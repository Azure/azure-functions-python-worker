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

use crate::pb::messages::{typed_data, ModelBindingData, RpcHttp, TypedData};

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
        typed_data::Data::ModelBindingData(m) => (
            "model_binding_data",
            model_binding_data_to_dict(py, m)?.into_any(),
        ),
        typed_data::Data::CollectionString(c) => (
            "collection_string",
            pyo3::types::PyList::new(py, &c.string)?.into_any(),
        ),
        typed_data::Data::CollectionBytes(c) => ("collection_bytes", {
            let l = pyo3::types::PyList::empty(py);
            for b in &c.bytes {
                l.append(PyBytes::new(py, b))?;
            }
            l.into_any()
        }),
        typed_data::Data::CollectionSint64(c) => (
            "collection_sint64",
            pyo3::types::PyList::new(py, &c.sint64)?.into_any(),
        ),
        typed_data::Data::CollectionDouble(c) => (
            "collection_double",
            pyo3::types::PyList::new(py, &c.double)?.into_any(),
        ),
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

/// Build the model_binding_data INPUT dict (deferred / SDK-type bindings).
fn model_binding_data_to_dict<'py>(
    py: Python<'py>,
    m: &ModelBindingData,
) -> Result<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("version", &m.version)?;
    d.set_item("source", &m.source)?;
    d.set_item("content_type", &m.content_type)?;
    d.set_item("content", PyBytes::new(py, &m.content))?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pb::messages::{typed_data, RpcHttp, TypedData};
    use pyo3::types::{PyDict, PyString, PyTuple};

    fn td(data: typed_data::Data) -> TypedData {
        TypedData { data: Some(data) }
    }

    /// Wrap a `("<kind>", <value>)` pair into the datum tuple the bridge exchanges.
    fn datum_tuple<'py>(
        py: Python<'py>,
        kind: &str,
        value: Bound<'py, PyAny>,
    ) -> Bound<'py, PyAny> {
        PyTuple::new(py, vec![PyString::new(py, kind).into_any(), value])
            .unwrap()
            .into_any()
    }

    #[test]
    fn scalar_string_round_trips() {
        Python::attach(|py| {
            let original = td(typed_data::Data::String("hello".into()));
            let tup = typed_data_to_tuple(py, &original).unwrap();
            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            assert_eq!(kind, "string");
            assert_eq!(tuple_to_typed_data(py, &tup).unwrap(), original);
        });
    }

    #[test]
    fn scalar_json_int_double_bytes_round_trip() {
        Python::attach(|py| {
            let cases = vec![
                td(typed_data::Data::Json("{\"a\":1}".into())),
                td(typed_data::Data::Int(42)),
                td(typed_data::Data::Double(2.5)),
                td(typed_data::Data::Bytes(vec![1, 2, 3, 255])),
            ];
            for original in cases {
                let tup = typed_data_to_tuple(py, &original).unwrap();
                assert_eq!(tuple_to_typed_data(py, &tup).unwrap(), original);
            }
        });
    }

    #[test]
    fn empty_payload_maps_to_none_both_ways() {
        Python::attach(|py| {
            let empty = TypedData { data: None };
            let tup = typed_data_to_tuple(py, &empty).unwrap();
            assert!(tup.is_none());
            assert_eq!(tuple_to_typed_data(py, &tup).unwrap(), empty);
        });
    }

    #[test]
    fn stream_variant_decodes_as_bytes() {
        Python::attach(|py| {
            let original = td(typed_data::Data::Stream(vec![9, 8, 7]));
            let tup = typed_data_to_tuple(py, &original).unwrap();
            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            assert_eq!(kind, "bytes");
            // Stream is inbound-only; it round-trips into the Bytes variant.
            assert_eq!(
                tuple_to_typed_data(py, &tup).unwrap(),
                td(typed_data::Data::Bytes(vec![9, 8, 7]))
            );
        });
    }

    #[test]
    fn http_input_expands_to_primitive_dict() {
        Python::attach(|py| {
            let mut headers = std::collections::HashMap::new();
            headers.insert("content-type".to_string(), "application/json".to_string());
            let http = RpcHttp {
                method: "POST".into(),
                url: "http://localhost/api/hello".into(),
                headers,
                body: Some(Box::new(td(typed_data::Data::String("payload".into())))),
                ..Default::default()
            };
            let tup = typed_data_to_tuple(py, &td(typed_data::Data::Http(Box::new(http)))).unwrap();

            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            assert_eq!(kind, "http");
            let d = tup.get_item(1).unwrap();
            let method: String = d.get_item("method").unwrap().extract().unwrap();
            assert_eq!(method, "POST");
            let url: String = d.get_item("url").unwrap().extract().unwrap();
            assert_eq!(url, "http://localhost/api/hello");
            let hdrs: std::collections::HashMap<String, String> =
                d.get_item("headers").unwrap().extract().unwrap();
            assert_eq!(
                hdrs.get("content-type").map(String::as_str),
                Some("application/json")
            );
            // Nested body is itself a datum tuple.
            let body = d.get_item("body").unwrap();
            let body_kind: String = body.get_item(0).unwrap().extract().unwrap();
            assert_eq!(body_kind, "string");
        });
    }

    #[test]
    fn http_output_dict_builds_rpc_http() {
        Python::attach(|py| {
            let d = PyDict::new(py);
            d.set_item("status_code", "200").unwrap();
            let hdrs = PyDict::new(py);
            hdrs.set_item("Content-Type", "text/plain").unwrap();
            d.set_item("headers", hdrs).unwrap();
            d.set_item(
                "body",
                datum_tuple(py, "string", PyString::new(py, "ok").into_any()),
            )
            .unwrap();
            let tup = datum_tuple(py, "http", d.into_any());

            let out = tuple_to_typed_data(py, &tup).unwrap();
            match out.data {
                Some(typed_data::Data::Http(h)) => {
                    assert_eq!(h.status_code, "200");
                    assert_eq!(
                        h.headers.get("Content-Type").map(String::as_str),
                        Some("text/plain")
                    );
                    match h.body.as_deref().and_then(|b| b.data.as_ref()) {
                        Some(typed_data::Data::String(s)) => assert_eq!(s.as_str(), "ok"),
                        other => panic!("unexpected http body: {other:?}"),
                    }
                }
                other => panic!("expected Http variant, got {other:?}"),
            }
        });
    }

    #[test]
    fn collection_string_maps_to_list() {
        Python::attach(|py| {
            let coll = crate::pb::messages::CollectionString {
                string: vec!["a".into(), "b".into(), "c".into()],
            };
            let tup =
                typed_data_to_tuple(py, &td(typed_data::Data::CollectionString(coll))).unwrap();
            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            assert_eq!(kind, "collection_string");
            let items: Vec<String> = tup.get_item(1).unwrap().extract().unwrap();
            assert_eq!(items, vec!["a", "b", "c"]);
        });
    }

    #[test]
    fn unsupported_outbound_type_errors() {
        Python::attach(|py| {
            let tup = datum_tuple(py, "totally_unknown", PyString::new(py, "x").into_any());
            assert!(tuple_to_typed_data(py, &tup).is_err());
        });
    }
}
