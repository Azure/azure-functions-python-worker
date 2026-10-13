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

use crate::pb::messages::{
    typed_data, CollectionModelBindingData, ModelBindingData, RpcHttp, RpcHttpCookie, TypedData,
};
use crate::pb::{
    nullable_bool, nullable_double, nullable_string, nullable_timestamp, NullableBool,
    NullableDouble, NullableString, NullableTimestamp,
};

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
        typed_data::Data::CollectionModelBindingData(c) => (
            "collection_model_binding_data",
            collection_model_binding_data_to_list(py, c)?.into_any(),
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

/// Build a collection_model_binding_data INPUT list of primitive dicts.
fn collection_model_binding_data_to_list<'py>(
    py: Python<'py>,
    collection: &CollectionModelBindingData,
) -> Result<Bound<'py, pyo3::types::PyList>> {
    let values = pyo3::types::PyList::empty(py);
    for model in &collection.model_binding_data {
        values.append(model_binding_data_to_dict(py, model)?)?;
    }
    Ok(values)
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
    let cookies = match d.get_item("cookies") {
        Ok(c) => http_cookies_from_list(&c)?,
        Err(_) => Vec::new(),
    };
    Ok(RpcHttp {
        status_code,
        headers,
        body,
        cookies,
        enable_content_negotiation: false,
        ..Default::default()
    })
}

/// Build the `RpcHttpCookie` list from the flat cookie dicts the bridge emits.
///
/// The bridge (bridge.py `_flatten_cookies`) pre-computes every field as a plain
/// primitive so the native path stays Python-protobuf-free: `same_site` is the
/// integer enum value, `expires` is epoch seconds (or `None`), and `max_age` is a
/// float (or `None`). We wrap the optional scalars in the `Nullable*` messages the
/// Host expects, matching the runtime's `parse_to_rpc_http_cookie_list`.
fn http_cookies_from_list(list_obj: &Bound<'_, PyAny>) -> Result<Vec<RpcHttpCookie>> {
    let mut cookies = Vec::new();
    if list_obj.is_none() {
        return Ok(cookies);
    }
    for item in list_obj.try_iter()? {
        let c = item?;
        let name: String = c.get_item("name")?.extract()?;
        let value: String = c.get_item("value")?.extract()?;
        let domain: String = c.get_item("domain")?.extract()?;
        let path: String = c.get_item("path")?.extract()?;
        let secure: bool = c.get_item("secure")?.extract()?;
        let http_only: bool = c.get_item("http_only")?.extract()?;
        let same_site: i32 = c.get_item("same_site")?.extract()?;

        let expires_obj = c.get_item("expires")?;
        let expires = if expires_obj.is_none() {
            None
        } else {
            let secs: i64 = expires_obj.extract()?;
            Some(NullableTimestamp {
                timestamp: Some(nullable_timestamp::Timestamp::Value(
                    prost_types::Timestamp {
                        seconds: secs,
                        nanos: 0,
                    },
                )),
            })
        };
        let max_age_obj = c.get_item("max_age")?;
        let max_age = if max_age_obj.is_none() {
            None
        } else {
            let v: f64 = max_age_obj.extract()?;
            Some(NullableDouble {
                double: Some(nullable_double::Double::Value(v)),
            })
        };

        cookies.push(RpcHttpCookie {
            name,
            value,
            domain: Some(NullableString {
                string: Some(nullable_string::String::Value(domain)),
            }),
            path: Some(NullableString {
                string: Some(nullable_string::String::Value(path)),
            }),
            expires,
            secure: Some(NullableBool {
                bool: Some(nullable_bool::Bool::Value(secure)),
            }),
            http_only: Some(NullableBool {
                bool: Some(nullable_bool::Bool::Value(http_only)),
            }),
            same_site,
            max_age,
        });
    }
    Ok(cookies)
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
    fn http_input_without_body_maps_body_to_none() {
        Python::attach(|py| {
            let http = RpcHttp {
                method: "GET".into(),
                url: "http://localhost/api/hello".into(),
                body: None,
                ..Default::default()
            };

            let tup = typed_data_to_tuple(py, &td(typed_data::Data::Http(Box::new(http)))).unwrap();
            assert!(tup.get_item(1).unwrap().get_item("body").unwrap().is_none());
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
    fn http_output_maps_cookie_fields_and_absent_body() {
        Python::attach(|py| {
            let cookie = PyDict::new(py);
            cookie.set_item("name", "session").unwrap();
            cookie.set_item("value", "abc").unwrap();
            cookie.set_item("domain", "example.com").unwrap();
            cookie.set_item("path", "/api").unwrap();
            cookie.set_item("secure", true).unwrap();
            cookie.set_item("http_only", true).unwrap();
            cookie.set_item("same_site", 2).unwrap();
            cookie.set_item("expires", 1_700_000_000_i64).unwrap();
            cookie.set_item("max_age", 3600.5).unwrap();

            let d = PyDict::new(py);
            d.set_item("status_code", "204").unwrap();
            d.set_item("headers", PyDict::new(py)).unwrap();
            d.set_item("body", py.None()).unwrap();
            d.set_item("cookies", vec![cookie]).unwrap();

            let tup = datum_tuple(py, "http", d.into_any());
            let out = tuple_to_typed_data(py, &tup).unwrap();
            let Some(typed_data::Data::Http(http)) = out.data else {
                panic!("expected Http variant");
            };

            assert_eq!(http.status_code, "204");
            assert!(http.body.is_none());
            assert_eq!(http.cookies.len(), 1);
            let cookie = &http.cookies[0];
            assert_eq!(cookie.name, "session");
            assert_eq!(cookie.value, "abc");
            assert_eq!(cookie.same_site, 2);
            assert_eq!(
                cookie.domain.as_ref().unwrap().string,
                Some(nullable_string::String::Value("example.com".into()))
            );
            assert_eq!(
                cookie.path.as_ref().unwrap().string,
                Some(nullable_string::String::Value("/api".into()))
            );
            assert_eq!(
                cookie.secure.as_ref().unwrap().bool,
                Some(nullable_bool::Bool::Value(true))
            );
            assert_eq!(
                cookie.http_only.as_ref().unwrap().bool,
                Some(nullable_bool::Bool::Value(true))
            );
            let timestamp = match cookie.expires.as_ref().unwrap().timestamp.as_ref() {
                Some(nullable_timestamp::Timestamp::Value(value)) => value,
                other => panic!("unexpected expires value: {other:?}"),
            };
            assert_eq!(timestamp.seconds, 1_700_000_000);
            assert_eq!(timestamp.nanos, 0);
            assert_eq!(
                cookie.max_age.as_ref().unwrap().double,
                Some(nullable_double::Double::Value(3600.5))
            );
        });
    }

    #[test]
    fn http_output_cookie_optional_times_can_be_none() {
        Python::attach(|py| {
            let cookie = PyDict::new(py);
            cookie.set_item("name", "session").unwrap();
            cookie.set_item("value", "abc").unwrap();
            cookie.set_item("domain", "").unwrap();
            cookie.set_item("path", "").unwrap();
            cookie.set_item("secure", false).unwrap();
            cookie.set_item("http_only", false).unwrap();
            cookie.set_item("same_site", 0).unwrap();
            cookie.set_item("expires", py.None()).unwrap();
            cookie.set_item("max_age", py.None()).unwrap();

            let d = PyDict::new(py);
            d.set_item("status_code", "200").unwrap();
            d.set_item("headers", PyDict::new(py)).unwrap();
            d.set_item("body", py.None()).unwrap();
            d.set_item("cookies", vec![cookie]).unwrap();

            let tup = datum_tuple(py, "http", d.into_any());
            let out = tuple_to_typed_data(py, &tup).unwrap();
            let Some(typed_data::Data::Http(http)) = out.data else {
                panic!("expected Http variant");
            };

            assert!(http.cookies[0].expires.is_none());
            assert!(http.cookies[0].max_age.is_none());
        });
    }

    #[test]
    fn http_output_cookie_list_can_be_none() {
        Python::attach(|py| {
            let d = PyDict::new(py);
            d.set_item("status_code", "200").unwrap();
            d.set_item("headers", PyDict::new(py)).unwrap();
            d.set_item("body", py.None()).unwrap();
            d.set_item("cookies", py.None()).unwrap();

            let tup = datum_tuple(py, "http", d.into_any());
            let out = tuple_to_typed_data(py, &tup).unwrap();
            let Some(typed_data::Data::Http(http)) = out.data else {
                panic!("expected Http variant");
            };

            assert!(http.cookies.is_empty());
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
    fn remaining_collection_variants_map_to_lists() {
        Python::attach(|py| {
            let bytes = crate::pb::messages::CollectionBytes {
                bytes: vec![vec![1, 2], vec![3, 4]],
            };
            let tup =
                typed_data_to_tuple(py, &td(typed_data::Data::CollectionBytes(bytes))).unwrap();
            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            let items: Vec<Vec<u8>> = tup.get_item(1).unwrap().extract().unwrap();
            assert_eq!(kind, "collection_bytes");
            assert_eq!(items, vec![vec![1, 2], vec![3, 4]]);

            let integers = crate::pb::messages::CollectionSInt64 {
                sint64: vec![-1, 0, 42],
            };
            let tup =
                typed_data_to_tuple(py, &td(typed_data::Data::CollectionSint64(integers))).unwrap();
            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            let items: Vec<i64> = tup.get_item(1).unwrap().extract().unwrap();
            assert_eq!(kind, "collection_sint64");
            assert_eq!(items, vec![-1, 0, 42]);

            let doubles = crate::pb::messages::CollectionDouble {
                double: vec![-1.5, 0.0, 42.25],
            };
            let tup =
                typed_data_to_tuple(py, &td(typed_data::Data::CollectionDouble(doubles))).unwrap();
            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            let items: Vec<f64> = tup.get_item(1).unwrap().extract().unwrap();
            assert_eq!(kind, "collection_double");
            assert_eq!(items, vec![-1.5, 0.0, 42.25]);
        });
    }

    #[test]
    fn model_binding_data_maps_to_primitive_dict() {
        Python::attach(|py| {
            let model = crate::pb::messages::ModelBindingData {
                version: "1.0".into(),
                source: "CosmosDB".into(),
                content_type: "application/json".into(),
                content: br#"{"id":"42"}"#.to_vec(),
            };
            let tup =
                typed_data_to_tuple(py, &td(typed_data::Data::ModelBindingData(model))).unwrap();

            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            assert_eq!(kind, "model_binding_data");
            let value = tup.get_item(1).unwrap();
            assert_eq!(
                value
                    .get_item("version")
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                "1.0"
            );
            assert_eq!(
                value
                    .get_item("source")
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                "CosmosDB"
            );
            assert_eq!(
                value
                    .get_item("content_type")
                    .unwrap()
                    .extract::<String>()
                    .unwrap(),
                "application/json"
            );
            assert_eq!(
                value
                    .get_item("content")
                    .unwrap()
                    .extract::<Vec<u8>>()
                    .unwrap(),
                br#"{"id":"42"}"#
            );
        });
    }

    #[test]
    fn collection_model_binding_data_maps_to_primitive_dicts() {
        Python::attach(|py| {
            let collection = crate::pb::messages::CollectionModelBindingData {
                model_binding_data: vec![
                    crate::pb::messages::ModelBindingData {
                        version: "1.0".into(),
                        source: "AzureEventHubsEventData".into(),
                        content_type: "application/octet-stream".into(),
                        content: b"event-1".to_vec(),
                    },
                    crate::pb::messages::ModelBindingData {
                        version: "1.0".into(),
                        source: "AzureEventHubsEventData".into(),
                        content_type: "application/octet-stream".into(),
                        content: b"event-2".to_vec(),
                    },
                ],
            };
            let value = td(typed_data::Data::CollectionModelBindingData(collection));
            let tup = typed_data_to_tuple(py, &value).unwrap();

            let kind: String = tup.get_item(0).unwrap().extract().unwrap();
            assert_eq!(kind, "collection_model_binding_data");
            let items = tup.get_item(1).unwrap();
            assert_eq!(items.len().unwrap(), 2);
            assert_eq!(
                items
                    .get_item(1)
                    .unwrap()
                    .get_item("content")
                    .unwrap()
                    .extract::<Vec<u8>>()
                    .unwrap(),
                b"event-2"
            );
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
