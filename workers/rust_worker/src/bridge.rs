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
/// the GIL without awaiting or deadlocking. See `docs/rustworker/logging-design.md`.
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
/// handing Python a `LogSink` (backed by `tx`) and the worker `request_id` so
/// it can stamp and route `RpcLog` messages onto the outbound stream.
pub fn configure(
    bridge_dir: &str,
    workers_dir: &str,
    app_dir: &str,
    host: &str,
    request_id: &str,
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
        bridge.call_method1("configure", (workers_dir, app_dir, host, request_id, sink))?;
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
        return Python::attach(|py| -> Result<Option<Vec<u8>>> {
            let bridge = py.import("bridge")?;
            let req = control::invocation_request_to_py(py, r)?;
            let resp = bridge.call_method1("handle_invocation_control", (req,))?;
            if resp.is_none() {
                return Ok(None);
            }
            let ir = control::py_to_invocation_response(py, &resp, &r.invocation_id)?;
            let out = StreamingMessage {
                request_id: rid,
                content: Some(Content::InvocationResponse(ir)),
            };
            Ok(Some(out.encode_to_vec()))
        });
    }

    Python::attach(|py| -> Result<Option<Vec<u8>>> {
        let bridge = py.import("bridge")?;

        // (verb name the runtime handler is dispatched under, request dict)
        let (verb, req): (&str, Bound<'_, PyAny>) = match &sm.content {
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

        let resp = bridge.call_method1("handle_control", (verb, req))?;
        if resp.is_none() {
            return Ok(None);
        }

        let content = match verb {
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

        let result = bridge.call_method1(
            "invoke_native",
            (&req.function_id, &req.invocation_id, inputs, meta),
        )?;

        let ok: bool = result.get_item(0)?.extract()?;
        if !ok {
            let exc: Option<String> = result.get_item(3)?.extract()?;
            return Ok(InvocationResponse {
                invocation_id: req.invocation_id.clone(),
                result: Some(StatusResult {
                    status: status_result::Status::Failure as i32,
                    exception: Some(RpcException {
                        message: exc.unwrap_or_default(),
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
