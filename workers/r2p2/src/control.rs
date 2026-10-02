// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// Control-plane codec. The invocation hot path lives in convert.rs;
// this module owns the *control* messages so the Python bridge never touches
// protobuf. For each inbound control verb we prost-decode the request into a
// Python dict the (unchanged) runtime handlers can read; the handler returns a
// pure-Python adapter response object, the bridge flattens it to a dict, and we
// map that dict back into a prost message here. Logging (RpcLog) and the
// StartStream handshake are also built here, so Python only ever produces
// dict/primitive values.

use anyhow::Result;
use prost_types::Duration;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::pb::messages::{
    BindingInfo, FunctionEnvironmentReloadRequest, FunctionEnvironmentReloadResponse,
    FunctionLoadRequest, FunctionLoadResponse, FunctionMetadataResponse, RpcException,
    RpcFunctionMetadata, RpcLog, RpcRetryOptions, StatusResult, StreamingMessage,
    WorkerInitRequest, WorkerInitResponse, WorkerMetadata,
};

// ---------------------------------------------------------------------------
// Small PyO3 extraction helpers (missing/None -> proto default).
// ---------------------------------------------------------------------------
fn get_str(d: &Bound<'_, PyAny>, key: &str) -> String {
    d.get_item(key)
        .ok()
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_default()
}

fn get_i32(d: &Bound<'_, PyAny>, key: &str) -> i32 {
    d.get_item(key)
        .ok()
        .and_then(|v| v.extract::<i32>().ok())
        .unwrap_or_default()
}

fn get_bool(d: &Bound<'_, PyAny>, key: &str) -> bool {
    d.get_item(key)
        .ok()
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or_default()
}

fn get_str_map(d: &Bound<'_, PyAny>, key: &str) -> std::collections::HashMap<String, String> {
    d.get_item(key)
        .ok()
        .and_then(|v| if v.is_none() { None } else { v.extract().ok() })
        .unwrap_or_default()
}

/// Optional nested dict item (`None`/missing -> `None`).
fn get_child<'py>(d: &Bound<'py, PyAny>, key: &str) -> Option<Bound<'py, PyAny>> {
    match d.get_item(key) {
        Ok(v) if !v.is_none() => Some(v),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// Inbound request (prost) -> Python dict for the runtime handlers.
// ---------------------------------------------------------------------------
/// Decode a `WorkerInitRequest` into the dict shape the runtime handler reads.
pub fn worker_init_req_to_py<'py>(
    py: Python<'py>,
    r: &WorkerInitRequest,
) -> Result<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("function_app_directory", &r.function_app_directory)?;
    d.set_item("capabilities", &r.capabilities)?;
    d.set_item("host_version", &r.host_version)?;
    Ok(d)
}

/// Decode a `FunctionEnvironmentReloadRequest` into the runtime handler's dict shape.
pub fn env_reload_req_to_py<'py>(
    py: Python<'py>,
    r: &FunctionEnvironmentReloadRequest,
) -> Result<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("function_app_directory", &r.function_app_directory)?;
    d.set_item("environment_variables", &r.environment_variables)?;
    Ok(d)
}

/// Decode a `FunctionLoadRequest` (incl. v1 `metadata.bindings`) into a dict.
pub fn function_load_req_to_py<'py>(
    py: Python<'py>,
    r: &FunctionLoadRequest,
) -> Result<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("function_id", &r.function_id)?;
    if let Some(md) = &r.metadata {
        let m = PyDict::new(py);
        m.set_item("name", &md.name)?;
        m.set_item("directory", &md.directory)?;
        m.set_item("script_file", &md.script_file)?;
        m.set_item("entry_point", &md.entry_point)?;
        // v1 reads metadata.bindings (Host-provided function.json bindings).
        let bindings = PyDict::new(py);
        for (name, bi) in &md.bindings {
            let b = PyDict::new(py);
            b.set_item("type", &bi.r#type)?;
            b.set_item("direction", bi.direction)?;
            b.set_item("data_type", bi.data_type)?;
            bindings.set_item(name, b)?;
        }
        m.set_item("bindings", bindings)?;
        d.set_item("metadata", m)?;
    }
    Ok(d)
}

// ---------------------------------------------------------------------------
// Adapter response dict (from Python) -> prost message.
// ---------------------------------------------------------------------------
fn py_to_rpc_exception(d: &Bound<'_, PyAny>) -> RpcException {
    RpcException {
        message: get_str(d, "message"),
        stack_trace: get_str(d, "stack_trace"),
        source: get_str(d, "source"),
        r#type: get_str(d, "type"),
        ..Default::default()
    }
}

fn py_to_status_result(d: Option<Bound<'_, PyAny>>) -> Option<StatusResult> {
    let d = d?;
    let exception = get_child(&d, "exception").map(|e| py_to_rpc_exception(&e));
    Some(StatusResult {
        status: get_i32(&d, "status"),
        exception,
        ..Default::default()
    })
}

fn py_to_worker_metadata(d: Option<Bound<'_, PyAny>>) -> Option<WorkerMetadata> {
    let d = d?;
    Some(WorkerMetadata {
        runtime_name: get_str(&d, "runtime_name"),
        runtime_version: get_str(&d, "runtime_version"),
        worker_version: get_str(&d, "worker_version"),
        worker_bitness: get_str(&d, "worker_bitness"),
        custom_properties: get_str_map(&d, "custom_properties"),
    })
}

fn secs_to_duration(d: &Bound<'_, PyAny>, key: &str) -> Option<Duration> {
    match d.get_item(key) {
        Ok(v) if !v.is_none() => v.extract::<i64>().ok().map(|s| Duration {
            seconds: s,
            nanos: 0,
        }),
        _ => None,
    }
}

fn py_to_retry_options(d: Option<Bound<'_, PyAny>>) -> Option<RpcRetryOptions> {
    let d = d?;
    Some(RpcRetryOptions {
        max_retry_count: get_i32(&d, "max_retry_count"),
        retry_strategy: get_i32(&d, "retry_strategy"),
        delay_interval: secs_to_duration(&d, "delay_interval_seconds"),
        minimum_interval: secs_to_duration(&d, "minimum_interval_seconds"),
        maximum_interval: secs_to_duration(&d, "maximum_interval_seconds"),
    })
}

fn py_to_rpc_function_metadata(d: &Bound<'_, PyAny>) -> Result<RpcFunctionMetadata> {
    let mut bindings = std::collections::HashMap::new();
    if let Some(bmap) = get_child(d, "bindings") {
        for item in bmap.call_method0("items")?.try_iter()? {
            let item = item?;
            let name: String = item.get_item(0)?.extract()?;
            let v = item.get_item(1)?;
            bindings.insert(
                name,
                BindingInfo {
                    r#type: get_str(&v, "type"),
                    data_type: get_i32(&v, "data_type"),
                    direction: get_i32(&v, "direction"),
                    ..Default::default()
                },
            );
        }
    }
    let raw_bindings = match get_child(d, "raw_bindings") {
        Some(rb) => rb.extract()?,
        None => Vec::new(),
    };
    Ok(RpcFunctionMetadata {
        name: get_str(d, "name"),
        directory: get_str(d, "directory"),
        script_file: get_str(d, "script_file"),
        entry_point: get_str(d, "entry_point"),
        bindings,
        is_proxy: get_bool(d, "is_proxy"),
        language: get_str(d, "language"),
        raw_bindings,
        function_id: get_str(d, "function_id"),
        managed_dependency_enabled: get_bool(d, "managed_dependency_enabled"),
        retry_options: py_to_retry_options(get_child(d, "retry_options")),
        properties: get_str_map(d, "properties"),
        ..Default::default()
    })
}

/// Map the adapter's flattened `WorkerInitResponse` dict back to prost.
pub fn py_to_worker_init_response(d: &Bound<'_, PyAny>) -> Result<WorkerInitResponse> {
    Ok(WorkerInitResponse {
        capabilities: get_str_map(d, "capabilities"),
        worker_metadata: py_to_worker_metadata(get_child(d, "worker_metadata")),
        result: py_to_status_result(get_child(d, "result")),
        ..Default::default()
    })
}

/// Map the adapter's flattened `FunctionMetadataResponse` dict back to prost.
pub fn py_to_function_metadata_response(d: &Bound<'_, PyAny>) -> Result<FunctionMetadataResponse> {
    let mut results = Vec::new();
    if let Some(list) = get_child(d, "function_metadata_results") {
        for item in list.try_iter()? {
            results.push(py_to_rpc_function_metadata(&item?)?);
        }
    }
    Ok(FunctionMetadataResponse {
        function_metadata_results: results,
        result: py_to_status_result(get_child(d, "result")),
        use_default_metadata_indexing: get_bool(d, "use_default_metadata_indexing"),
    })
}

/// Map the adapter's flattened `FunctionLoadResponse` dict back to prost.
pub fn py_to_function_load_response(d: &Bound<'_, PyAny>) -> Result<FunctionLoadResponse> {
    Ok(FunctionLoadResponse {
        function_id: get_str(d, "function_id"),
        result: py_to_status_result(get_child(d, "result")),
        ..Default::default()
    })
}

/// Map the adapter's flattened `FunctionEnvironmentReloadResponse` dict back to prost.
pub fn py_to_env_reload_response(
    d: &Bound<'_, PyAny>,
) -> Result<FunctionEnvironmentReloadResponse> {
    Ok(FunctionEnvironmentReloadResponse {
        worker_metadata: py_to_worker_metadata(get_child(d, "worker_metadata")),
        capabilities: get_str_map(d, "capabilities"),
        result: py_to_status_result(get_child(d, "result")),
    })
}

// ---------------------------------------------------------------------------
// Logging: a flat fields dict -> StreamingMessage(rpc_log=...).
// ---------------------------------------------------------------------------
/// Build an `RpcLog` `StreamingMessage` from a flat fields dict.
pub fn py_log_to_streaming_message(
    d: &Bound<'_, PyAny>,
    request_id: &str,
) -> Result<StreamingMessage> {
    let rpc_log = RpcLog {
        invocation_id: get_str(d, "invocation_id"),
        category: get_str(d, "category"),
        level: get_i32(d, "level"),
        message: get_str(d, "message"),
        event_id: get_str(d, "event_id"),
        log_category: get_i32(d, "log_category"),
        ..Default::default()
    };
    Ok(StreamingMessage {
        request_id: request_id.to_string(),
        content: Some(crate::pb::messages::streaming_message::Content::RpcLog(
            rpc_log,
        )),
    })
}

/// Build the initial StartStream handshake message.
pub fn start_stream_message(worker_id: &str) -> StreamingMessage {
    use crate::pb::messages::{streaming_message::Content, StartStream};
    StreamingMessage {
        request_id: String::new(),
        content: Some(Content::StartStream(StartStream {
            worker_id: worker_id.to_string(),
        })),
    }
}

// ---------------------------------------------------------------------------
// Invocation control path (deferred / http-v2). Unlike the native fast path
// (bridge::invoke), these invocations run the runtime's standard
// `invocation_request` handler, which needs protobuf-shaped inputs and produces
// protobuf-shaped outputs. We exchange the same datum tuples convert.rs uses:
// Rust prost-decodes the request into a Python dict, the bridge builds adapter
// TypedData/ParameterBinding objects, runs the handler, and returns a flattened
// InvocationResponse dict we map back to prost here.
// ---------------------------------------------------------------------------
use crate::convert::{tuple_to_typed_data, typed_data_to_tuple};
use crate::pb::messages::{
    parameter_binding, InvocationRequest, InvocationResponse, ParameterBinding,
};

/// Decode an `InvocationRequest` into a dict of datum tuples for the runtime's
/// standard `invocation_request` handler (deferred / http-v2 control path).
pub fn invocation_request_to_py<'py>(
    py: Python<'py>,
    r: &InvocationRequest,
) -> Result<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("invocation_id", &r.invocation_id)?;
    d.set_item("function_id", &r.function_id)?;

    let inputs = pyo3::types::PyList::empty(py);
    for pb in &r.input_data {
        let td = match &pb.rpc_data {
            Some(parameter_binding::RpcData::Data(td)) => typed_data_to_tuple(py, td)?,
            _ => py.None().into_bound(py),
        };
        let entry = pyo3::types::PyTuple::new(
            py,
            [pyo3::types::PyString::new(py, &pb.name).into_any(), td],
        )?;
        inputs.append(entry)?;
    }
    d.set_item("input_data", inputs)?;

    let meta = PyDict::new(py);
    for (k, td) in &r.trigger_metadata {
        meta.set_item(k, typed_data_to_tuple(py, td)?)?;
    }
    d.set_item("trigger_metadata", meta)?;

    let tc = PyDict::new(py);
    if let Some(t) = &r.trace_context {
        tc.set_item("trace_parent", &t.trace_parent)?;
        tc.set_item("trace_state", &t.trace_state)?;
        tc.set_item("attributes", &t.attributes)?;
    } else {
        tc.set_item("trace_parent", "")?;
        tc.set_item("trace_state", "")?;
        tc.set_item("attributes", PyDict::new(py))?;
    }
    d.set_item("trace_context", tc)?;

    let rc = PyDict::new(py);
    if let Some(rt) = &r.retry_context {
        rc.set_item("retry_count", rt.retry_count)?;
        rc.set_item("max_retry_count", rt.max_retry_count)?;
        match &rt.exception {
            Some(ex) => {
                let e = PyDict::new(py);
                e.set_item("message", &ex.message)?;
                e.set_item("stack_trace", &ex.stack_trace)?;
                e.set_item("source", &ex.source)?;
                rc.set_item("exception", e)?;
            }
            None => rc.set_item("exception", py.None())?,
        }
    } else {
        rc.set_item("retry_count", 0)?;
        rc.set_item("max_retry_count", 0)?;
        rc.set_item("exception", py.None())?;
    }
    d.set_item("retry_context", rc)?;

    Ok(d)
}

/// Map the runtime's flattened `InvocationResponse` dict back to prost.
pub fn py_to_invocation_response(
    py: Python<'_>,
    d: &Bound<'_, PyAny>,
    invocation_id: &str,
) -> Result<InvocationResponse> {
    let return_value = match get_child(d, "return_value") {
        Some(t) => Some(tuple_to_typed_data(py, &t)?),
        None => None,
    };

    let mut output_data = Vec::new();
    if let Some(list) = get_child(d, "output_data") {
        for item in list.try_iter()? {
            let item = item?;
            let name = get_str(&item, "name");
            let data = match get_child(&item, "data") {
                Some(t) => Some(tuple_to_typed_data(py, &t)?),
                None => None,
            };
            output_data.push(ParameterBinding {
                name,
                rpc_data: data.map(parameter_binding::RpcData::Data),
            });
        }
    }

    Ok(InvocationResponse {
        invocation_id: invocation_id.to_string(),
        output_data,
        return_value,
        result: py_to_status_result(get_child(d, "result")),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pb::messages::{
        parameter_binding, streaming_message::Content, BindingInfo, FunctionLoadRequest,
        InvocationRequest, ParameterBinding, RpcFunctionMetadata, TypedData, WorkerInitRequest,
    };
    use crate::pb::messages::{streaming_message, typed_data};
    use pyo3::types::{PyDict, PyList, PyString, PyTuple};

    fn datum_tuple<'py>(py: Python<'py>, kind: &str, value: &str) -> Bound<'py, PyAny> {
        PyTuple::new(
            py,
            vec![
                PyString::new(py, kind).into_any(),
                PyString::new(py, value).into_any(),
            ],
        )
        .unwrap()
        .into_any()
    }

    // --- pure (no interpreter) -------------------------------------------
    #[test]
    fn start_stream_carries_worker_id_and_empty_request_id() {
        let msg = start_stream_message("worker-123");
        assert_eq!(msg.request_id, "");
        match msg.content {
            Some(Content::StartStream(s)) => assert_eq!(s.worker_id, "worker-123"),
            other => panic!("expected StartStream, got {other:?}"),
        }
    }

    // --- inbound request (prost -> dict) ---------------------------------
    #[test]
    fn worker_init_request_decodes_to_dict() {
        Python::attach(|py| {
            let mut caps = std::collections::HashMap::new();
            caps.insert("RawHttpBodyBytes".to_string(), "true".to_string());
            let r = WorkerInitRequest {
                function_app_directory: "/home/site/wwwroot".into(),
                host_version: "4.1.0".into(),
                capabilities: caps,
                ..Default::default()
            };
            let d = worker_init_req_to_py(py, &r).unwrap();
            let dir: String = d
                .get_item("function_app_directory")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(dir, "/home/site/wwwroot");
            let hv: String = d
                .get_item("host_version")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(hv, "4.1.0");
        });
    }

    #[test]
    fn function_load_request_decodes_nested_bindings() {
        Python::attach(|py| {
            let mut bindings = std::collections::HashMap::new();
            bindings.insert(
                "req".to_string(),
                BindingInfo {
                    r#type: "httpTrigger".into(),
                    direction: 0,
                    data_type: 0,
                    ..Default::default()
                },
            );
            let r = FunctionLoadRequest {
                function_id: "fid-1".into(),
                metadata: Some(RpcFunctionMetadata {
                    name: "hello".into(),
                    entry_point: "main".into(),
                    bindings,
                    ..Default::default()
                }),
                ..Default::default()
            };
            let d = function_load_req_to_py(py, &r).unwrap();
            let fid: String = d
                .get_item("function_id")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(fid, "fid-1");
            let meta = d.get_item("metadata").unwrap().unwrap();
            let name: String = meta.get_item("name").unwrap().extract().unwrap();
            assert_eq!(name, "hello");
            let btype: String = meta
                .get_item("bindings")
                .unwrap()
                .get_item("req")
                .unwrap()
                .get_item("type")
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(btype, "httpTrigger");
        });
    }

    #[test]
    fn invocation_request_decodes_inputs_and_metadata() {
        Python::attach(|py| {
            let mut trigger_metadata = std::collections::HashMap::new();
            trigger_metadata.insert(
                "Query".to_string(),
                TypedData {
                    data: Some(typed_data::Data::String("q".into())),
                },
            );
            let r = InvocationRequest {
                invocation_id: "inv-1".into(),
                function_id: "fid-1".into(),
                input_data: vec![ParameterBinding {
                    name: "req".into(),
                    rpc_data: Some(parameter_binding::RpcData::Data(TypedData {
                        data: Some(typed_data::Data::String("body".into())),
                    })),
                }],
                trigger_metadata,
                ..Default::default()
            };
            let d = invocation_request_to_py(py, &r).unwrap();
            let inv: String = d
                .get_item("invocation_id")
                .unwrap()
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(inv, "inv-1");
            let inputs = d.get_item("input_data").unwrap().unwrap();
            let first = inputs.get_item(0).unwrap();
            let name: String = first.get_item(0).unwrap().extract().unwrap();
            assert_eq!(name, "req");
            let datum_kind: String = first
                .get_item(1)
                .unwrap()
                .get_item(0)
                .unwrap()
                .extract()
                .unwrap();
            assert_eq!(datum_kind, "string");
        });
    }

    // --- adapter response dict (dict -> prost) ---------------------------
    #[test]
    fn worker_init_response_maps_capabilities_and_status() {
        Python::attach(|py| {
            let d = PyDict::new(py);
            let caps = PyDict::new(py);
            caps.set_item("WorkerStatus", "true").unwrap();
            d.set_item("capabilities", caps).unwrap();
            let result = PyDict::new(py);
            result.set_item("status", 1).unwrap();
            d.set_item("result", result).unwrap();

            let resp = py_to_worker_init_response(&d.into_any()).unwrap();
            assert_eq!(
                resp.capabilities.get("WorkerStatus").map(String::as_str),
                Some("true")
            );
            assert_eq!(resp.result.unwrap().status, 1);
        });
    }

    #[test]
    fn function_load_response_maps_id_and_status() {
        Python::attach(|py| {
            let d = PyDict::new(py);
            d.set_item("function_id", "fid-1").unwrap();
            let result = PyDict::new(py);
            result.set_item("status", 1).unwrap();
            d.set_item("result", result).unwrap();

            let resp = py_to_function_load_response(&d.into_any()).unwrap();
            assert_eq!(resp.function_id, "fid-1");
            assert_eq!(resp.result.unwrap().status, 1);
        });
    }

    #[test]
    fn invocation_response_maps_return_value_and_result() {
        Python::attach(|py| {
            let d = PyDict::new(py);
            d.set_item("return_value", datum_tuple(py, "string", "ok"))
                .unwrap();
            d.set_item("output_data", PyList::empty(py)).unwrap();
            let result = PyDict::new(py);
            result.set_item("status", 1).unwrap();
            d.set_item("result", result).unwrap();

            let resp = py_to_invocation_response(py, &d.into_any(), "inv-1").unwrap();
            assert_eq!(resp.invocation_id, "inv-1");
            assert_eq!(resp.result.unwrap().status, 1);
            match resp.return_value.and_then(|t| t.data) {
                Some(typed_data::Data::String(s)) => assert_eq!(s, "ok"),
                other => panic!("unexpected return_value: {other:?}"),
            }
        });
    }

    // --- logging ----------------------------------------------------------
    #[test]
    fn log_dict_builds_rpc_log_streaming_message() {
        Python::attach(|py| {
            let d = PyDict::new(py);
            d.set_item("invocation_id", "inv-1").unwrap();
            d.set_item("category", "worker").unwrap();
            d.set_item("level", 4).unwrap();
            d.set_item("message", "hello logs").unwrap();

            let msg = py_log_to_streaming_message(&d.into_any(), "req-9").unwrap();
            assert_eq!(msg.request_id, "req-9");
            match msg.content {
                Some(streaming_message::Content::RpcLog(l)) => {
                    assert_eq!(l.invocation_id, "inv-1");
                    assert_eq!(l.category, "worker");
                    assert_eq!(l.level, 4);
                    assert_eq!(l.message, "hello logs");
                }
                other => panic!("expected RpcLog, got {other:?}"),
            }
        });
    }
}
