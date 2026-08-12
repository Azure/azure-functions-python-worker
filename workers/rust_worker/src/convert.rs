// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// Conversion layer: prost `TypedData` <-> a Python "datum tuple".
//
// The hot path (invocation) is decoded/encoded with prost in Rust, so no Python
// protobuf is touched. The Python bridge still needs the values, but in the
// runtime's own protobuf-free currency: the `Datum(value, type)` intermediate.
//
// To keep the FFI boundary cheap and free of protobuf, we exchange a compact
// "datum tuple":
//   * scalar  -> ("string"|"json"|"int"|"double"|"bytes", <primitive>)
//   * http in -> ("http", {method,url,headers,params,query,body:<datum tuple|None>})
//   * http out-> ("http", {status_code:str, headers:{..}, body:<datum tuple|None>})
//   * empty   -> None
// The bridge turns these into/out of real `Datum` objects (nested `Datum` dicts
// for http) that the runtime's binding encode/decode expect. Rust only ever
// deals with primitives + dicts; Python owns the `Datum` nesting.

use anyhow::{anyhow, Result};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyString, PyTuple};

use crate::pb::messages::{typed_data, RpcHttp, TypedData};

/// prost `TypedData` -> Python datum tuple (or `None` for empty payloads).
pub fn typed_data_to_tuple<'py>(py: Python<'py>, td: &TypedData) -> Result<Bound<'py, PyAny>> {
    let data = match &td.data {
        Some(d) => d,
        None => return Ok(py.None().into_bound(py)),
    };
    let (type_str, value): (&str, Bound<'py, PyAny>) = match data {
        typed_data::Data::String(s) => ("string", PyString::new(py, s).into_any()),
        typed_data::Data::Json(s) => ("json", PyString::new(py, s).into_any()),
        typed_data::Data::Bytes(b) => ("bytes", PyBytes::new(py, b).into_any()),
        typed_data::Data::Stream(b) => ("bytes", PyBytes::new(py, b).into_any()),
        typed_data::Data::Int(i) => (
            "int",
            i.into_pyobject(py).map_err(|e| anyhow!("{e}"))?.into_any(),
        ),
        typed_data::Data::Double(f) => (
            "double",
            f.into_pyobject(py).map_err(|e| anyhow!("{e}"))?.into_any(),
        ),
        typed_data::Data::Http(h) => ("http", http_in_to_dict(py, h)?.into_any()),
        other => {
            return Err(anyhow!(
                "native path: unsupported inbound TypedData variant: {:?}",
                std::mem::discriminant(other)
            ))
        }
    };
    let tup = PyTuple::new(py, vec![PyString::new(py, type_str).into_any(), value])?;
    Ok(tup.into_any())
}

/// Build the http INPUT dict of primitives the bridge expands into a Datum.
fn http_in_to_dict<'py>(py: Python<'py>, h: &RpcHttp) -> Result<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("method", &h.method)?;
    d.set_item("url", &h.url)?;
    d.set_item("headers", &h.headers)?;
    d.set_item("params", &h.params)?;
    d.set_item("query", &h.query)?;
    let body = match &h.body {
        Some(b) => typed_data_to_tuple(py, b)?,
        None => py.None().into_bound(py),
    };
    d.set_item("body", body)?;
    Ok(d)
}

/// Python datum tuple (or `None`) -> prost `TypedData`.
pub fn tuple_to_typed_data(py: Python<'_>, obj: &Bound<'_, PyAny>) -> Result<TypedData> {
    if obj.is_none() {
        return Ok(TypedData { data: None });
    }
    let type_str: String = obj.get_item(0)?.extract()?;
    let val = obj.get_item(1)?;
    let data = match type_str.as_str() {
        "string" => typed_data::Data::String(val.extract()?),
        "json" => typed_data::Data::Json(val.extract()?),
        "int" => typed_data::Data::Int(val.extract()?),
        "double" => typed_data::Data::Double(val.extract()?),
        "bytes" => typed_data::Data::Bytes(val.extract::<Vec<u8>>()?),
        "http" => typed_data::Data::Http(Box::new(http_out_from_dict(py, &val)?)),
        other => {
            return Err(anyhow!(
                "native path: unsupported outbound datum type: {other}"
            ))
        }
    };
    Ok(TypedData { data: Some(data) })
}

/// Build a prost `RpcHttp` from the http OUTPUT dict the bridge produced.
fn http_out_from_dict(py: Python<'_>, d: &Bound<'_, PyAny>) -> Result<RpcHttp> {
    let status_code: String = d.get_item("status_code")?.extract()?;
    let headers: std::collections::HashMap<String, String> = d.get_item("headers")?.extract()?;
    let body_obj = d.get_item("body")?;
    let body = if body_obj.is_none() {
        None
    } else {
        Some(Box::new(tuple_to_typed_data(py, &body_obj)?))
    };
    Ok(RpcHttp {
        status_code,
        headers,
        body,
        enable_content_negotiation: false,
        ..Default::default()
    })
}
