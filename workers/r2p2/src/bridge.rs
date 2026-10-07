// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// PyO3 glue: the "thin waist" FFI into the embedded CPython runtime. Each call
// attaches to the interpreter, imports the `bridge` module and forwards bytes.
// The surface is deliberately narrow (configure / start_stream / handle /
// shutdown) to mirror the in-process contract the Python dispatcher uses.

use anyhow::{anyhow, Result};
use bytes::Bytes;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyString, PyTuple};
use tokio::sync::mpsc::UnboundedSender;

use crate::control;
use crate::convert::{tuple_to_typed_data, typed_data_to_tuple};
use crate::pb::messages::{
    parameter_binding, status_result, streaming_message, InvocationRequest, InvocationResponse,
    ParameterBinding, RpcException, StatusResult, StreamingMessage,
};
use prost::Message as _;

/// A Rust-owned sink handed to the Python logging handler. Its `emit` is a
/// non-blocking, thread-safe enqueue onto the single outbound gRPC channel, so
/// Python can push `RpcLog` StreamingMessage bytes from any thread while holding
/// the GIL without awaiting or deadlocking.
#[pyclass]
pub struct LogSink {
    tx: UnboundedSender<Bytes>,
    request_id: String,
}

#[pymethods]
impl LogSink {
    /// Enqueue one already-serialized StreamingMessage(rpc_log=...) onto the
    /// outbound stream. Never panics: a closed channel (worker shutting down) is
    /// swallowed so logging can't crash user code.
    fn emit(&self, data: &[u8]) {
        let _ = self.tx.send(Bytes::copy_from_slice(data));
    }

    /// Build + enqueue an RpcLog StreamingMessage from a flat fields dict. Lets
    /// the Python log handler stay protobuf-free: it passes primitives and Rust
    /// (prost) owns the wire encoding. `request_id` is the worker request id.
    fn emit_log(&self, fields: &Bound<'_, PyAny>) {
        match control::py_log_to_streaming_message(fields, &self.request_id) {
            Ok(sm) => {
                let _ = self.tx.send(Bytes::from(sm.encode_to_vec()));
            }
            Err(e) => {
                eprintln!("LanguageWorkerConsoleLog ERROR: emit_log failed: {e}");
            }
        }
    }
}

/// Add the bridge directory to `sys.path` and call `bridge.configure(...)`,
/// handing Python a `LogSink` (backed by `tx`) plus the worker `request_id` and
/// `worker_id` so it can stamp and route `RpcLog` messages onto the outbound
/// stream and log them with the same identifiers as the classic proxy worker.
pub fn configure(
    bridge_dir: &str,
    workers_dir: &str,
    app_dir: &str,
    host: &str,
    request_id: &str,
    worker_id: &str,
    tx: UnboundedSender<Bytes>,
) -> Result<()> {
    Python::attach(|py| -> Result<()> {
        let sys = py.import("sys")?;
        let path = sys
            .getattr("path")?
            .cast_into::<PyList>()
            .map_err(|e| anyhow!("sys.path is not a list: {e}"))?;
        path.insert(0, bridge_dir)?;
        // Make the worker's bundled runtime importable BEFORE `import bridge`.
        // configure() re-prioritizes sys.path afterwards (customer deps first).
        if !workers_dir.is_empty() {
            path.insert(1, workers_dir)?;
        }

        let bridge = py.import("bridge")?;
        let sink = Py::new(
            py,
            LogSink {
                tx,
                request_id: request_id.to_string(),
            },
        )?;
        bridge.call_method1(
            "configure",
            (workers_dir, app_dir, host, request_id, sink, worker_id),
        )?;
        Ok(())
    })
}

/// Build the initial `StreamingMessage(start_stream=...)` payload. Built in Rust
/// (prost) so Python never touches protobuf.
pub fn start_stream(worker_id: &str) -> Result<Vec<u8>> {
    Ok(control::start_stream_message(worker_id).encode_to_vec())
}

/// Route one inbound control-plane `StreamingMessage` (raw bytes) and return the
/// response bytes, or `None` when no reply is warranted. Invocations are routed
/// separately (see `invoke`); this handles worker_init / functions_metadata /
/// function_load / env_reload / worker_status. Requests are prost-decoded here,
/// the (unchanged) runtime handler runs against a protobuf-free adapter, and its
/// returned dict is prost-encoded back onto the wire.
pub fn handle(raw: &[u8]) -> Result<Option<Vec<u8>>> {
    let sm = StreamingMessage::decode(raw)?;
    let request_id = sm.request_id.clone();
    use streaming_message::Content;

    // worker_status is answered locally without touching Python (fast scale
    // probe), mirroring the previous bridge behavior.
    if let Some(Content::WorkerStatusRequest(_)) = &sm.content {
        let out = StreamingMessage {
            request_id,
            content: Some(Content::WorkerStatusResponse(Default::default())),
        };
        return Ok(Some(out.encode_to_vec()));
    }

    // Invocation control path (deferred / http-v2). Runs the runtime's standard
    // invocation_request handler through the protobuf-free adapter, unlike the
    // native fast path in `invoke`.
    if let Some(Content::InvocationRequest(r)) = &sm.content {
        let rid = sm.request_id.clone();
        let invocation_id = r.invocation_id.clone();
        let result = Python::attach(|py| -> Result<Option<Vec<u8>>> {
            let bridge = py.import("bridge")?;
            let req = control::invocation_request_to_py(py, r)?;
            let resp = bridge.call_method1("handle_invocation_control", (req,))?;
            if resp.is_none() {
                return Ok(None);
            }
            let ir = control::py_to_invocation_response(py, &resp, &r.invocation_id)?;
            let out = StreamingMessage {
                request_id: rid.clone(),
                content: Some(Content::InvocationResponse(ir)),
            };
            Ok(Some(out.encode_to_vec()))
        });
        return match result {
            Ok(response) => Ok(response),
            Err(error) => {
                let response = InvocationResponse {
                    invocation_id,
                    result: Some(StatusResult {
                        status: status_result::Status::Failure as i32,
                        exception: Some(RpcException {
                            message: format!("{error:#}"),
                            ..Default::default()
                        }),
                        ..Default::default()
                    }),
                    ..Default::default()
                };
                let out = StreamingMessage {
                    request_id: rid,
                    content: Some(Content::InvocationResponse(response)),
                };
                Ok(Some(out.encode_to_vec()))
            }
        };
    }

    Python::attach(|py| -> Result<Option<Vec<u8>>> {
        let bridge = py.import("bridge")?;

        // (request type the runtime handler is dispatched under, request dict)
        let (request_type, req): (&str, Bound<'_, PyAny>) = match &sm.content {
            Some(Content::WorkerInitRequest(r)) => (
                "worker_init_request",
                control::worker_init_req_to_py(py, r)?.into_any(),
            ),
            Some(Content::FunctionsMetadataRequest(_)) => {
                ("functions_metadata_request", PyDict::new(py).into_any())
            }
            Some(Content::FunctionLoadRequest(r)) => (
                "function_load_request",
                control::function_load_req_to_py(py, r)?.into_any(),
            ),
            Some(Content::FunctionEnvironmentReloadRequest(r)) => (
                "function_environment_reload_request",
                control::env_reload_req_to_py(py, r)?.into_any(),
            ),
            other => {
                let _ = bridge.call_method1(
                    "log_unhandled",
                    (format!("{:?}", other.as_ref().map(std::mem::discriminant)),),
                );
                return Ok(None);
            }
        };

        let resp = bridge.call_method1("handle_control", (request_type, req))?;
        if resp.is_none() {
            return Ok(None);
        }

        let content = match request_type {
            "worker_init_request" => {
                Content::WorkerInitResponse(control::py_to_worker_init_response(&resp)?)
            }
            "functions_metadata_request" => {
                Content::FunctionMetadataResponse(control::py_to_function_metadata_response(&resp)?)
            }
            "function_load_request" => {
                Content::FunctionLoadResponse(control::py_to_function_load_response(&resp)?)
            }
            "function_environment_reload_request" => Content::FunctionEnvironmentReloadResponse(
                control::py_to_env_reload_response(&resp)?,
            ),
            _ => unreachable!(),
        };

        let out = StreamingMessage {
            request_id,
            content: Some(content),
        };
        Ok(Some(out.encode_to_vec()))
    })
}

/// Whether invocations for `function_id` must take the pure-Python control path
/// (`handle`) rather than the native prost path. True for deferred (SDK-type)
/// bindings and http-v2 streaming functions, which native_invocation.py does not
/// support. Cached per function_id on the Python side; defaults to `false` on any
/// error so the fast native path is preserved.
pub fn requires_control_path(function_id: &str) -> bool {
    Python::attach(|py| -> Result<bool> {
        let bridge = py.import("bridge")?;
        let r = bridge.call_method1("requires_control_path", (function_id,))?;
        Ok(r.extract::<bool>()?)
    })
    .unwrap_or(false)
}

/// Native invocation path: the InvocationRequest was decoded from the
/// wire by prost in Rust, so NO Python protobuf is touched here. We convert each
/// input `TypedData` to a datum tuple, call `bridge.invoke_native`, and rebuild a
/// prost `InvocationResponse` from the returned datum tuples.
pub fn invoke(req: &InvocationRequest) -> Result<InvocationResponse> {
    Python::attach(|py| -> Result<InvocationResponse> {
        let bridge = py.import("bridge")?;

        let inputs = PyList::empty(py);
        for pb in &req.input_data {
            let td = match &pb.rpc_data {
                Some(parameter_binding::RpcData::Data(td)) => td,
                _ => continue,
            };
            let tup = typed_data_to_tuple(py, td)?;
            let entry = PyTuple::new(py, vec![PyString::new(py, &pb.name).into_any(), tup])?;
            inputs.append(entry)?;
        }

        let meta = PyDict::new(py);
        for (k, td) in &req.trigger_metadata {
            let tup = typed_data_to_tuple(py, td)?;
            meta.set_item(k, tup)?;
        }

        // Trace context (W3C traceparent/tracestate) so the native path can
        // parent customer OpenTelemetry spans and Azure Monitor export, matching
        // the control path's configure_opentelemetry. Empty when the Host sends
        // no trace context.
        let (trace_parent, trace_state) = match &req.trace_context {
            Some(tc) => (tc.trace_parent.as_str(), tc.trace_state.as_str()),
            None => ("", ""),
        };

        let retry_context = match &req.retry_context {
            Some(rc) => {
                let d = PyDict::new(py);
                d.set_item("retry_count", rc.retry_count)?;
                d.set_item("max_retry_count", rc.max_retry_count)?;
                if let Some(exc) = &rc.exception {
                    let exception = PyDict::new(py);
                    exception.set_item("message", &exc.message)?;
                    exception.set_item("stack_trace", &exc.stack_trace)?;
                    exception.set_item("source", &exc.source)?;
                    exception.set_item("type", &exc.r#type)?;
                    d.set_item("exception", exception)?;
                }
                d.into_any()
            }
            None => py.None().into_bound(py),
        };

        let result = bridge.call_method1(
            "invoke_native",
            (
                &req.function_id,
                &req.invocation_id,
                inputs,
                meta,
                trace_parent,
                trace_state,
                retry_context,
            ),
        )?;

        let ok: bool = result.get_item(0)?.extract()?;
        if !ok {
            let exc: Option<String> = result.get_item(3)?.extract()?;
            let stack_trace: Option<String> = result.get_item(4)?.extract()?;
            return Ok(InvocationResponse {
                invocation_id: req.invocation_id.clone(),
                result: Some(StatusResult {
                    status: status_result::Status::Failure as i32,
                    exception: Some(RpcException {
                        message: exc.unwrap_or_default(),
                        stack_trace: stack_trace.unwrap_or_default(),
                        ..Default::default()
                    }),
                    ..Default::default()
                }),
                ..Default::default()
            });
        }

        let ret_obj = result.get_item(1)?;
        let return_value = if ret_obj.is_none() {
            None
        } else {
            Some(tuple_to_typed_data(py, &ret_obj)?)
        };

        let mut output_data = Vec::new();
        let out_list = result.get_item(2)?;
        for item in out_list.try_iter()? {
            let item = item?;
            let name: String = item.get_item(0)?.extract()?;
            let tup = item.get_item(1)?;
            let td = tuple_to_typed_data(py, &tup)?;
            output_data.push(ParameterBinding {
                name,
                rpc_data: Some(parameter_binding::RpcData::Data(td)),
            });
        }

        Ok(InvocationResponse {
            invocation_id: req.invocation_id.clone(),
            output_data,
            return_value,
            result: Some(StatusResult {
                status: status_result::Status::Success as i32,
                ..Default::default()
            }),
        })
    })
}

/// Best-effort teardown of the runtime threadpool / bridge loop.
pub fn shutdown() {
    let _ = Python::attach(|py| -> Result<()> {
        let bridge = py.import("bridge")?;
        bridge.call_method0("shutdown")?;
        Ok(())
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pb::messages::typed_data;
    use crate::pb::messages::{
        parameter_binding, status_result::Status, streaming_message::Content,
        FunctionEnvironmentReloadRequest, FunctionLoadRequest, FunctionsMetadataRequest,
        RetryContext, RpcSharedMemory, RpcTraceContext, TypedData, WorkerInitRequest,
        WorkerStatusRequest,
    };
    use pyo3::types::{PyDict, PyModule};
    use std::ffi::CString;
    use std::sync::Mutex;

    static TEST_BRIDGE_LOCK: Mutex<()> = Mutex::new(());

    fn install_test_bridge() {
        const SOURCE: &str = r#"
calls = []

def configure(workers_dir, app_dir, host, request_id, sink, worker_id):
    calls.append(("configure", workers_dir, app_dir, host, request_id, worker_id))
    sink.emit(b"configured")

def requires_control_path(function_id):
    calls.append(("requires_control_path", function_id))
    return function_id == "control"

def handle_control(request_type, request):
    calls.append(("handle_control", request_type))
    if request_type == "worker_init_request":
        assert request["host_version"] == "4.0.0"
        return {"capabilities": {"TestCapability": "true"}, "result": {"status": 1}}
    if request_type == "functions_metadata_request":
        return None
    if request_type == "function_load_request":
        return {"function_id": request["function_id"], "result": {"status": 1}}
    if request_type == "function_environment_reload_request":
        return {"capabilities": {}, "result": {"status": 1}}
    raise AssertionError(f"unexpected request type: {request_type}")

def handle_invocation_control(request):
    calls.append(("handle_invocation_control", request["invocation_id"]))
    if request["invocation_id"] == "invocation-none":
        return None
    if request["invocation_id"] == "invocation-error":
        return {
            "return_value": ("unsupported", "value"),
            "output_data": [],
            "result": {"status": 1},
        }
    return {
        "return_value": ("string", "control-result"),
        "output_data": [],
        "result": {"status": 1},
    }

def invoke_native(function_id, invocation_id, inputs, metadata,
                  trace_parent, trace_state, retry_context):
    calls.append(("invoke_native", function_id, invocation_id))
    if function_id == "fail":
        return (False, None, [], "native failure", "native stack")
    if function_id == "none":
        assert trace_parent == ""
        assert trace_state == ""
        assert retry_context is None
        return (True, None, [], None, None)
    assert inputs == [("input", ("string", "value"))]
    assert metadata == {"meta": ("int", 7)}
    assert trace_parent == "trace-parent"
    assert trace_state == "trace-state"
    assert retry_context["retry_count"] == 2
    assert retry_context["max_retry_count"] == 5
    assert retry_context["exception"]["message"] == "retry"
        return (True, ("string", "native-result"),
            [("output", ("int", 42))], None, None)

def log_unhandled(value):
    calls.append(("log_unhandled", value))

def shutdown():
    calls.append(("shutdown",))
"#;

        Python::attach(|py| {
            let source = CString::new(SOURCE).unwrap();
            let module = PyModule::from_code(py, &source, c"bridge_test.py", c"bridge").unwrap();
            py.import("sys")
                .unwrap()
                .getattr("modules")
                .unwrap()
                .set_item("bridge", module)
                .unwrap();
        });
    }

    fn remove_test_bridge() {
        Python::attach(|py| {
            let sys = py.import("sys").unwrap();
            sys.getattr("modules").unwrap().del_item("bridge").unwrap();
            let path = sys.getattr("path").unwrap();
            for entry in [
                "test-bridge-dir",
                "test-empty-workers-bridge-dir",
                "test-workers-dir",
            ] {
                while path
                    .call_method1("__contains__", (entry,))
                    .unwrap()
                    .extract::<bool>()
                    .unwrap()
                {
                    path.call_method1("remove", (entry,)).unwrap();
                }
            }
        });
    }

    #[test]
    fn start_stream_returns_encoded_handshake() {
        let encoded = start_stream("worker-123").unwrap();
        let message = StreamingMessage::decode(encoded.as_slice()).unwrap();

        assert_eq!(message.request_id, "");
        match message.content {
            Some(Content::StartStream(start)) => assert_eq!(start.worker_id, "worker-123"),
            other => panic!("expected StartStream, got {other:?}"),
        }
    }

    #[test]
    fn log_sink_emit_copies_bytes_to_outbound_channel() {
        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        let sink = LogSink {
            tx,
            request_id: "request-1".into(),
        };
        let mut data = vec![1, 2, 3];

        sink.emit(&data);
        data[0] = 9;

        assert_eq!(rx.try_recv().unwrap(), Bytes::from_static(&[1, 2, 3]));
    }

    #[test]
    fn log_sink_emit_ignores_closed_channel() {
        let (tx, rx) = tokio::sync::mpsc::unbounded_channel();
        drop(rx);
        let sink = LogSink {
            tx,
            request_id: "request-1".into(),
        };

        sink.emit(&[1, 2, 3]);
    }

    #[test]
    fn log_sink_emit_log_builds_streaming_message() {
        Python::attach(|py| {
            let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
            let sink = LogSink {
                tx,
                request_id: "request-1".into(),
            };
            let fields = PyDict::new(py);
            fields.set_item("invocation_id", "invocation-1").unwrap();
            fields.set_item("category", "Function.Test").unwrap();
            fields.set_item("level", 2).unwrap();
            fields.set_item("message", "hello").unwrap();

            sink.emit_log(&fields.into_any());

            let bytes = rx.try_recv().unwrap();
            let message = StreamingMessage::decode(bytes).unwrap();
            assert_eq!(message.request_id, "request-1");
            match message.content {
                Some(Content::RpcLog(log)) => {
                    assert_eq!(log.invocation_id, "invocation-1");
                    assert_eq!(log.category, "Function.Test");
                    assert_eq!(log.level, 2);
                    assert_eq!(log.message, "hello");
                }
                other => panic!("expected RpcLog, got {other:?}"),
            }
        });
    }

    #[test]
    fn handle_worker_status_responds_without_python_bridge() {
        let request = StreamingMessage {
            request_id: "request-1".into(),
            content: Some(Content::WorkerStatusRequest(WorkerStatusRequest {})),
        };

        let encoded = handle(&request.encode_to_vec()).unwrap().unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();

        assert_eq!(response.request_id, "request-1");
        assert!(matches!(
            response.content,
            Some(Content::WorkerStatusResponse(_))
        ));
    }

    #[test]
    fn handle_rejects_malformed_streaming_message() {
        assert!(handle(&[0xff, 0xff]).is_err());
    }

    #[test]
    fn python_bridge_contract_routes_control_and_native_messages() {
        let _lock = TEST_BRIDGE_LOCK.lock().unwrap();
        install_test_bridge();

        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        configure(
            "test-bridge-dir",
            "test-workers-dir",
            "test-app-dir",
            "localhost",
            "request-1",
            "worker-1",
            tx,
        )
        .unwrap();
        assert_eq!(rx.try_recv().unwrap(), Bytes::from_static(b"configured"));

        let (tx, mut rx) = tokio::sync::mpsc::unbounded_channel();
        configure(
            "test-empty-workers-bridge-dir",
            "",
            "test-app-dir",
            "localhost",
            "request-2",
            "worker-2",
            tx,
        )
        .unwrap();
        assert_eq!(rx.try_recv().unwrap(), Bytes::from_static(b"configured"));

        assert!(requires_control_path("control"));
        assert!(!requires_control_path("native"));

        let worker_init = StreamingMessage {
            request_id: "request-init".into(),
            content: Some(Content::WorkerInitRequest(WorkerInitRequest {
                host_version: "4.0.0".into(),
                ..Default::default()
            })),
        };
        let encoded = handle(&worker_init.encode_to_vec()).unwrap().unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();
        assert_eq!(response.request_id, "request-init");
        match response.content {
            Some(Content::WorkerInitResponse(response)) => {
                assert_eq!(response.capabilities["TestCapability"], "true");
                assert_eq!(response.result.unwrap().status, Status::Success as i32);
            }
            other => panic!("expected WorkerInitResponse, got {other:?}"),
        }

        let metadata = StreamingMessage {
            request_id: "request-metadata".into(),
            content: Some(Content::FunctionsMetadataRequest(
                FunctionsMetadataRequest::default(),
            )),
        };
        assert!(handle(&metadata.encode_to_vec()).unwrap().is_none());

        let function_load = StreamingMessage {
            request_id: "request-load".into(),
            content: Some(Content::FunctionLoadRequest(FunctionLoadRequest {
                function_id: "function-1".into(),
                ..Default::default()
            })),
        };
        let encoded = handle(&function_load.encode_to_vec()).unwrap().unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();
        match response.content {
            Some(Content::FunctionLoadResponse(response)) => {
                assert_eq!(response.function_id, "function-1");
            }
            other => panic!("expected FunctionLoadResponse, got {other:?}"),
        }

        let environment_reload = StreamingMessage {
            request_id: "request-reload".into(),
            content: Some(Content::FunctionEnvironmentReloadRequest(
                FunctionEnvironmentReloadRequest {
                    function_app_directory: "test-app-dir".into(),
                    environment_variables: Default::default(),
                },
            )),
        };
        let encoded = handle(&environment_reload.encode_to_vec())
            .unwrap()
            .unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();
        assert!(matches!(
            response.content,
            Some(Content::FunctionEnvironmentReloadResponse(_))
        ));

        let invocation_control = StreamingMessage {
            request_id: "request-control".into(),
            content: Some(Content::InvocationRequest(InvocationRequest {
                invocation_id: "invocation-control".into(),
                function_id: "control".into(),
                ..Default::default()
            })),
        };
        let encoded = handle(&invocation_control.encode_to_vec())
            .unwrap()
            .unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();
        match response.content {
            Some(Content::InvocationResponse(response)) => {
                assert_eq!(response.invocation_id, "invocation-control");
                assert_eq!(
                    response.return_value.unwrap().data,
                    Some(typed_data::Data::String("control-result".into()))
                );
            }
            other => panic!("expected InvocationResponse, got {other:?}"),
        }

        let invocation_error = StreamingMessage {
            request_id: "request-error".into(),
            content: Some(Content::InvocationRequest(InvocationRequest {
                invocation_id: "invocation-error".into(),
                function_id: "control".into(),
                ..Default::default()
            })),
        };
        let encoded = handle(&invocation_error.encode_to_vec()).unwrap().unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();
        assert_eq!(response.request_id, "request-error");
        match response.content {
            Some(Content::InvocationResponse(response)) => {
                assert_eq!(response.invocation_id, "invocation-error");
                let result = response.result.unwrap();
                assert_eq!(result.status, Status::Failure as i32);
                assert!(result
                    .exception
                    .unwrap()
                    .message
                    .contains("unsupported outbound datum type"));
            }
            other => panic!("expected InvocationResponse, got {other:?}"),
        }

        let invocation_none = StreamingMessage {
            request_id: "request-none".into(),
            content: Some(Content::InvocationRequest(InvocationRequest {
                invocation_id: "invocation-none".into(),
                function_id: "control".into(),
                ..Default::default()
            })),
        };
        assert!(handle(&invocation_none.encode_to_vec()).unwrap().is_none());

        let unhandled = StreamingMessage {
            request_id: "request-unhandled".into(),
            content: None,
        };
        assert!(handle(&unhandled.encode_to_vec()).unwrap().is_none());

        let mut trigger_metadata = std::collections::HashMap::new();
        trigger_metadata.insert(
            "meta".into(),
            TypedData {
                data: Some(typed_data::Data::Int(7)),
            },
        );
        let request = InvocationRequest {
            invocation_id: "invocation-native".into(),
            function_id: "native".into(),
            input_data: vec![
                ParameterBinding {
                    name: "input".into(),
                    rpc_data: Some(parameter_binding::RpcData::Data(TypedData {
                        data: Some(typed_data::Data::String("value".into())),
                    })),
                },
                ParameterBinding {
                    name: "shared".into(),
                    rpc_data: Some(parameter_binding::RpcData::RpcSharedMemory(
                        RpcSharedMemory::default(),
                    )),
                },
            ],
            trigger_metadata,
            trace_context: Some(RpcTraceContext {
                trace_parent: "trace-parent".into(),
                trace_state: "trace-state".into(),
                ..Default::default()
            }),
            retry_context: Some(RetryContext {
                retry_count: 2,
                max_retry_count: 5,
                exception: Some(RpcException {
                    message: "retry".into(),
                    stack_trace: "stack".into(),
                    source: "source".into(),
                    r#type: "ValueError".into(),
                    ..Default::default()
                }),
            }),
        };
        let response = invoke(&request).unwrap();
        assert_eq!(response.invocation_id, "invocation-native");
        assert_eq!(response.result.unwrap().status, Status::Success as i32);
        assert_eq!(
            response.return_value.unwrap().data,
            Some(typed_data::Data::String("native-result".into()))
        );
        assert_eq!(response.output_data.len(), 1);
        assert_eq!(response.output_data[0].name, "output");
        assert_eq!(
            response.output_data[0].rpc_data,
            Some(parameter_binding::RpcData::Data(TypedData {
                data: Some(typed_data::Data::Int(42)),
            }))
        );

        let failure = invoke(&InvocationRequest {
            invocation_id: "invocation-failure".into(),
            function_id: "fail".into(),
            ..Default::default()
        })
        .unwrap();
        let result = failure.result.unwrap();
        assert_eq!(result.status, Status::Failure as i32);
        let exception = result.exception.unwrap();
        assert_eq!(exception.message, "native failure");
        assert_eq!(exception.stack_trace, "native stack");

        let no_value = invoke(&InvocationRequest {
            invocation_id: "invocation-none".into(),
            function_id: "none".into(),
            ..Default::default()
        })
        .unwrap();
        assert!(no_value.return_value.is_none());
        assert!(no_value.output_data.is_empty());
        assert_eq!(no_value.result.unwrap().status, Status::Success as i32);

        shutdown();
        remove_test_bridge();
        assert!(!requires_control_path("missing-module"));
        shutdown();
    }
}
