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
    if let Some(v) = control_path_cache().lock().unwrap().get(function_id) {
        return *v;
    }
    let v = bridge::requires_control_path(function_id);
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

fn parse_args() -> Result<Args> {
    // Accept both the Host-style (--functions-*) and short flags. Unknown flags
    // are ignored so the Host can pass extras we don't consume.
    let raw: Vec<String> = std::env::args().skip(1).collect();
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
        .unwrap_or("rust-worker-0")
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
