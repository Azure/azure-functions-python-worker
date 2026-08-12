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
use pyo3::types::{PyBytes, PyDict, PyList, PyString, PyTuple};
use tokio::sync::mpsc::UnboundedSender;

use crate::convert::{tuple_to_typed_data, typed_data_to_tuple};
use crate::pb::messages::{
    parameter_binding, status_result, InvocationRequest, InvocationResponse, ParameterBinding,
    RpcException, StatusResult,
};

/// A Rust-owned sink handed to the Python logging handler. Its `emit` is a
/// non-blocking, thread-safe enqueue onto the single outbound gRPC channel, so
/// Python can push `RpcLog` StreamingMessage bytes from any thread while holding
/// the GIL without awaiting or deadlocking. See `docs/rustworker/logging-design.md`.
#[pyclass]
pub struct LogSink {
    tx: UnboundedSender<Bytes>,
}

#[pymethods]
impl LogSink {
    /// Enqueue one already-serialized StreamingMessage(rpc_log=...) onto the
    /// outbound stream. Never panics: a closed channel (worker shutting down) is
    /// swallowed so logging can't crash user code.
    fn emit(&self, data: &[u8]) {
        let _ = self.tx.send(Bytes::copy_from_slice(data));
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
        // Make the worker's bundled deps (google.protobuf lives here) importable
        // BEFORE `import bridge` runs `import protos` at module load. configure()
        // re-prioritizes sys.path afterwards (customer deps first); this just
        // ensures the control-plane protobuf resolves to the worker's own copy.
        if !workers_dir.is_empty() {
            path.insert(1, workers_dir)?;
        }

        let bridge = py.import("bridge")?;
        let sink = Py::new(py, LogSink { tx })?;
        bridge.call_method1("configure", (workers_dir, app_dir, host, request_id, sink))?;
        Ok(())
    })
}

/// Build the initial `StreamingMessage(start_stream=...)` payload.
pub fn start_stream(worker_id: &str) -> Result<Vec<u8>> {
    Python::attach(|py| -> Result<Vec<u8>> {
        let bridge = py.import("bridge")?;
        let r = bridge.call_method1("start_stream", (worker_id,))?;
        Ok(r.extract::<Vec<u8>>()?)
    })
}

/// Route one inbound `StreamingMessage` (raw bytes) and return the response
/// bytes, or `None` when no reply is warranted.
pub fn handle(raw: &[u8]) -> Result<Option<Vec<u8>>> {
    Python::attach(|py| -> Result<Option<Vec<u8>>> {
        let bridge = py.import("bridge")?;
        let arg = PyBytes::new(py, raw);
        let r = bridge.call_method1("handle", (arg,))?;
        if r.is_none() {
            Ok(None)
        } else {
            Ok(Some(r.extract::<Vec<u8>>()?))
        }
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
