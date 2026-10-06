// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.
//
// Owns the gRPC transport (tonic bidirectional EventStream) and embeds CPython
// (PyO3). It dials the Functions Host, sends StartStream, then for every inbound
// StreamingMessage forwards the raw bytes to the Python bridge and streams the
// bridge's response bytes back: a native transport shell driving the Python v2
// runtime in-process.

mod bridge;
mod codec;
mod control;
mod convert;
mod log;
mod pb;

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use anyhow::{anyhow, Context, Result};
use bytes::Bytes;
use codec::BytesCodec;
use http::uri::PathAndQuery;
use prost::Message as _;
use tokio::sync::mpsc;
use tokio_stream::wrappers::UnboundedReceiverStream;
use tonic::transport::Endpoint;
use tonic::Request;

use pb::messages::{streaming_message, StreamingMessage};

const EVENT_STREAM_PATH: &str = "/AzureFunctionsRpcMessages.FunctionRpc/EventStream";

/// Per-function cache of the native-vs-control-path routing decision. Populated
/// once per function_id (the answer is fixed after indexing) so the hot path
/// only pays a GIL round-trip to the bridge on first sight of a function.
fn control_path_cache() -> &'static Mutex<HashMap<String, bool>> {
    static CACHE: OnceLock<Mutex<HashMap<String, bool>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Whether invocations for `function_id` must take the pure-Python control path
/// (deferred bindings / http-v2 streaming). Memoized per function_id.
fn needs_control_path(function_id: &str) -> bool {
    needs_control_path_with(function_id, bridge::requires_control_path)
}

fn needs_control_path_with(function_id: &str, resolve: impl FnOnce(&str) -> bool) -> bool {
    if let Some(v) = control_path_cache().lock().unwrap().get(function_id) {
        return *v;
    }
    let v = resolve(function_id);
    control_path_cache()
        .lock()
        .unwrap()
        .insert(function_id.to_string(), v);
    v
}

struct Args {
    uri: String,
    worker_id: String,
    request_id: String,
    grpc_max_message_length: Option<usize>,
    workers_dir: String,
    app_dir: String,
    bridge_dir: String,
    host: String,
}

fn get<'a>(map: &'a std::collections::HashMap<String, String>, keys: &[&str]) -> Option<&'a str> {
    for k in keys {
        if let Some(v) = map.get(*k) {
            return Some(v.as_str());
        }
    }
    None
}

fn grpc_max_message_length(map: &HashMap<String, String>) -> Result<Option<usize>> {
    get(
        map,
        &["functions-grpc-max-message-length", "grpcMaxMessageLength"],
    )
    .filter(|value| !value.is_empty())
    .map(str::parse)
    .transpose()
    .context("invalid gRPC max message length")
}

fn parse_args() -> Result<Args> {
    parse_args_from(std::env::args().skip(1))
}

fn parse_args_from(raw: impl IntoIterator<Item = String>) -> Result<Args> {
    // Accept both the Host-style (--functions-*) and short flags. Unknown flags
    // are ignored so the Host can pass extras we don't consume.
    let raw: Vec<String> = raw.into_iter().collect();
    let mut map = std::collections::HashMap::new();
    let mut i = 0;
    while i < raw.len() {
        let a = &raw[i];
        if let Some(key) = a.strip_prefix("--") {
            if let Some(eq) = key.find('=') {
                map.insert(key[..eq].to_string(), key[eq + 1..].to_string());
                i += 1;
            } else if i + 1 < raw.len() && !raw[i + 1].starts_with("--") {
                map.insert(key.to_string(), raw[i + 1].clone());
                i += 2;
            } else {
                map.insert(key.to_string(), String::new());
                i += 1;
            }
        } else {
            i += 1;
        }
    }

    // Build the gRPC URI. Prefer --functions-uri; otherwise host+port.
    let uri = if let Some(u) = get(&map, &["functions-uri", "uri"]) {
        let u = u.to_string();
        if u.starts_with("http://") || u.starts_with("https://") {
            u
        } else {
            format!("http://{u}")
        }
    } else {
        let host = get(&map, &["host"]).unwrap_or("127.0.0.1");
        let port =
            get(&map, &["port"]).ok_or_else(|| anyhow!("missing --port / --functions-uri"))?;
        format!("http://{host}:{port}")
    };

    let worker_id = get(&map, &["functions-worker-id", "workerId", "worker-id"])
        .unwrap_or("r2p2-0")
        .to_string();
    let request_id = get(&map, &["functions-request-id", "requestId", "request-id"])
        .unwrap_or("rust-request-0")
        .to_string();

    // The Host launches the worker from the worker directory (where the binary,
    // the `bridge/` package, and the pruned site-packages live). When the paths
    // are not passed explicitly (the production `worker.config.json` omits them),
    // derive them from the executable's own location: workers_dir is the
    // directory holding the binary and bridge_dir is its `bridge/` subdirectory.
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()));
    let default_workers_dir = exe_dir
        .as_ref()
        .map(|d| d.to_string_lossy().into_owned())
        .unwrap_or_default();
    let default_bridge_dir = exe_dir
        .as_ref()
        .map(|d| d.join("bridge").to_string_lossy().into_owned())
        .unwrap_or_default();

    let workers_dir = get(&map, &["workers-dir"])
        .map(str::to_string)
        .unwrap_or(default_workers_dir);
    let bridge_dir = get(&map, &["bridge-dir"])
        .map(str::to_string)
        .unwrap_or(default_bridge_dir);

    Ok(Args {
        uri,
        worker_id,
        request_id,
        grpc_max_message_length: grpc_max_message_length(&map)?,
        workers_dir,
        app_dir: get(&map, &["functions-app-directory", "app-dir"])
            .unwrap_or("")
            .to_string(),
        bridge_dir,
        host: get(&map, &["host"]).unwrap_or("127.0.0.1").to_string(),
    })
}

/// Route + service one inbound `StreamingMessage` (invocations take the native
/// prost path; everything else the pure-Python control path). Returns the
/// response bytes to send back, or `None`. Runs on its own task so many
/// invocations are in flight at once.
async fn process_message(raw: Bytes) -> Result<Option<Vec<u8>>> {
    let decoded = StreamingMessage::decode(raw.clone()).ok();
    let invocation_fid = decoded.as_ref().and_then(|sm| match &sm.content {
        Some(streaming_message::Content::InvocationRequest(r)) => Some(r.function_id.clone()),
        _ => None,
    });

    // Invocations for deferred-binding / http-v2 functions must take the
    // pure-Python control path (bridge::handle -> runtime.invocation_request);
    // the native prost path does not support them. Everything else (and all
    // control-plane messages) keeps its existing route.
    if let Some(fid) = invocation_fid {
        if needs_control_path(&fid) {
            return tokio::task::spawn_blocking(move || bridge::handle(&raw))
                .await
                .context("bridge control-path invoke join")?;
        }
        tokio::task::spawn_blocking(move || -> Result<Option<Vec<u8>>> {
            let sm = StreamingMessage::decode(raw)?;
            let req = match sm.content {
                Some(streaming_message::Content::InvocationRequest(r)) => r,
                _ => unreachable!(),
            };
            let response = bridge::invoke(&req)?;
            let out = StreamingMessage {
                request_id: sm.request_id,
                content: Some(streaming_message::Content::InvocationResponse(response)),
            };
            Ok(Some(out.encode_to_vec()))
        })
        .await
        .context("native invoke task join")?
    } else {
        tokio::task::spawn_blocking(move || bridge::handle(&raw))
            .await
            .context("bridge task join")?
    }
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<()> {
    let args = parse_args()?;
    log::info(&format!(
        "Starting proxy worker. Worker ID: {}, Request ID: {}, Host Address: {}",
        args.worker_id, args.request_id, args.uri
    ));

    // Outbound channel is the SINGLE writer to the gRPC stream: both invocation
    // responses and RpcLog messages (pushed by Python via the LogSink) flow
    // through it. Unbounded so a Python logging call from any thread never
    // blocks and needs no tokio context. Created BEFORE configure so logs
    // emitted during worker_init are buffered until the stream drains.
    let (tx, rx) = mpsc::unbounded_channel::<Bytes>();

    // Embed CPython and wire up the Python bridge before opening the channel.
    bridge::configure(
        &args.bridge_dir,
        &args.workers_dir,
        &args.app_dir,
        &args.host,
        &args.request_id,
        &args.worker_id,
        tx.clone(),
    )
    .context("configure python bridge")?;
    log::info("Python bridge configured.");

    let endpoint = Endpoint::from_shared(args.uri.clone())
        .context("invalid host uri")?
        .tcp_nodelay(true);
    let channel = endpoint
        .connect()
        .await
        .context("connect to Functions Host")?;
    let mut grpc = tonic::client::Grpc::new(channel);
    if let Some(limit) = args.grpc_max_message_length {
        grpc = grpc
            .max_decoding_message_size(limit)
            .max_encoding_message_size(limit);
    }
    grpc.ready()
        .await
        .map_err(|e| anyhow!("gRPC channel not ready: {e}"))?;
    log::info(&format!("Successfully opened gRPC channel to {}", args.uri));

    // First message on the stream must be StartStream (built by the bridge).
    let start = bridge::start_stream(&args.worker_id)?;
    tx.send(Bytes::from(start))
        .map_err(|e| anyhow!("send StartStream: {e}"))?;
    log::info("Sent StartStream to the Host.");

    let outbound = UnboundedReceiverStream::new(rx);
    let request = Request::new(outbound);
    let path = PathAndQuery::from_static(EVENT_STREAM_PATH);
    let response = grpc
        .streaming(request, path, BytesCodec)
        .await
        .map_err(|e| anyhow!("EventStream open failed: {e}"))?;
    let mut inbound = response.into_inner();

    loop {
        match inbound.message().await {
            Ok(Some(msg)) => {
                let raw: Bytes = msg;
                // Dispatch each message CONCURRENTLY: spawn a task and immediately
                // loop back to read the next inbound message. Awaiting the handler
                // here would serialize every invocation at the transport, capping
                // throughput to one in-flight call. The Host correlates responses
                // by id, so out-of-order replies on the shared outbound channel
                // are fine.
                let tx2 = tx.clone();
                tokio::spawn(async move {
                    match process_message(raw).await {
                        Ok(Some(bytes)) => {
                            let _ = tx2.send(Bytes::from(bytes));
                        }
                        Ok(None) => {}
                        Err(e) => log::error(&format!("handler error: {e:#}")),
                    }
                });
            }
            Ok(None) => {
                log::info("Host closed the gRPC stream.");
                break;
            }
            Err(e) => {
                log::error(&format!("gRPC stream error: {e}"));
                break;
            }
        }
    }

    bridge::shutdown();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(values: &[&str]) -> Result<Args> {
        parse_args_from(values.iter().map(|value| (*value).to_string()))
    }

    #[test]
    fn parses_host_grpc_message_limit_aliases() {
        for key in ["functions-grpc-max-message-length", "grpcMaxMessageLength"] {
            let map = HashMap::from([(key.to_string(), "28312683".to_string())]);
            assert_eq!(grpc_max_message_length(&map).unwrap(), Some(28_312_683));
        }
    }

    #[test]
    fn rejects_invalid_grpc_message_limit() {
        let map = HashMap::from([(
            "functions-grpc-max-message-length".to_string(),
            "invalid".to_string(),
        )]);
        assert!(grpc_max_message_length(&map).is_err());
    }

    #[test]
    fn empty_grpc_message_limit_is_not_configured() {
        let map = HashMap::from([(
            "functions-grpc-max-message-length".to_string(),
            String::new(),
        )]);

        assert_eq!(grpc_max_message_length(&map).unwrap(), None);
    }

    #[test]
    fn parses_host_style_arguments_and_equals_syntax() {
        let parsed = args(&[
            "ignored-positional",
            "--functions-uri=localhost:5001",
            "--functions-worker-id",
            "worker-1",
            "--functions-request-id=request-1",
            "--functions-grpc-max-message-length",
            "1024",
            "--workers-dir",
            "C:\\worker",
            "--bridge-dir=C:\\worker\\bridge",
            "--functions-app-directory",
            "C:\\app",
            "--host",
            "host-name",
            "--unknown-flag",
        ])
        .unwrap();

        assert_eq!(parsed.uri, "http://localhost:5001");
        assert_eq!(parsed.worker_id, "worker-1");
        assert_eq!(parsed.request_id, "request-1");
        assert_eq!(parsed.grpc_max_message_length, Some(1024));
        assert_eq!(parsed.workers_dir, "C:\\worker");
        assert_eq!(parsed.bridge_dir, "C:\\worker\\bridge");
        assert_eq!(parsed.app_dir, "C:\\app");
        assert_eq!(parsed.host, "host-name");
    }

    #[test]
    fn parses_host_and_port_with_default_ids() {
        let parsed = args(&[
            "--host",
            "localhost",
            "--port",
            "5002",
            "--workers-dir",
            "workers",
            "--bridge-dir",
            "bridge",
        ])
        .unwrap();

        assert_eq!(parsed.uri, "http://localhost:5002");
        assert_eq!(parsed.worker_id, "r2p2-0");
        assert_eq!(parsed.request_id, "rust-request-0");
        assert_eq!(parsed.grpc_max_message_length, None);
        assert_eq!(parsed.app_dir, "");
    }

    #[test]
    fn preserves_uri_scheme_and_accepts_short_aliases() {
        let parsed = args(&[
            "--uri",
            "https://localhost:5003",
            "--worker-id",
            "worker-3",
            "--requestId",
            "request-3",
            "--grpcMaxMessageLength",
            "2048",
            "--workers-dir",
            "workers",
            "--bridge-dir",
            "bridge",
            "--app-dir",
            "app",
        ])
        .unwrap();

        assert_eq!(parsed.uri, "https://localhost:5003");
        assert_eq!(parsed.worker_id, "worker-3");
        assert_eq!(parsed.request_id, "request-3");
        assert_eq!(parsed.grpc_max_message_length, Some(2048));
        assert_eq!(parsed.app_dir, "app");
        assert_eq!(parsed.host, "127.0.0.1");
    }

    #[test]
    fn rejects_arguments_without_uri_or_port() {
        let error = args(&["--host", "localhost"]).err().unwrap();

        assert!(error
            .to_string()
            .contains("missing --port / --functions-uri"));
    }

    #[test]
    fn derives_worker_paths_from_current_executable() {
        let parsed = args(&["--uri", "localhost:5004"]).unwrap();
        let executable_directory = std::env::current_exe()
            .unwrap()
            .parent()
            .unwrap()
            .to_path_buf();

        assert_eq!(
            parsed.workers_dir,
            executable_directory.to_string_lossy().into_owned()
        );
        assert_eq!(
            parsed.bridge_dir,
            executable_directory
                .join("bridge")
                .to_string_lossy()
                .into_owned()
        );
    }

    #[test]
    fn control_path_decision_is_cached_for_true_and_false_values() {
        assert!(needs_control_path_with("test-cache-true", |function_id| {
            assert_eq!(function_id, "test-cache-true");
            true
        }));
        assert!(needs_control_path_with("test-cache-true", |_| {
            panic!("cached true value should not be resolved twice")
        }));

        assert!(!needs_control_path_with(
            "test-cache-false",
            |function_id| {
                assert_eq!(function_id, "test-cache-false");
                false
            }
        ));
        assert!(!needs_control_path_with("test-cache-false", |_| {
            panic!("cached false value should not be resolved twice")
        }));
    }

    #[tokio::test]
    async fn process_message_routes_worker_status_request() {
        let request = StreamingMessage {
            request_id: "request-status".into(),
            content: Some(streaming_message::Content::WorkerStatusRequest(
                pb::messages::WorkerStatusRequest {},
            )),
        };

        let encoded = process_message(Bytes::from(request.encode_to_vec()))
            .await
            .unwrap()
            .unwrap();
        let response = StreamingMessage::decode(encoded.as_slice()).unwrap();

        assert_eq!(response.request_id, "request-status");
        assert!(matches!(
            response.content,
            Some(streaming_message::Content::WorkerStatusResponse(_))
        ));
    }

    #[tokio::test]
    async fn process_message_propagates_malformed_wire_error() {
        let error = process_message(Bytes::from_static(&[0xff, 0xff]))
            .await
            .err()
            .unwrap();

        assert!(error
            .to_string()
            .contains("failed to decode Protobuf message"));
    }
}
