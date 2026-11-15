# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Canonical 7-Phase Lifecycle Specifications across all 3 Python Worker Generations:
  1. init            — Worker Initialization (StartStream + WorkerInitRequest)
  2. specialization  — Worker Specialization (FunctionEnvironmentReloadRequest, Consumption only)
  3. metadata        — Worker Metadata & Indexing (FunctionsMetadataRequest)
  4. function_load   — Worker Functions Load (FunctionLoadRequest, V1 primary)
  5. invocation      — Worker Invocation (InvocationRequest)
  6. worker_status   — Worker Status Health/Scale Check (WorkerStatusRequest)
  7. worker_logs     — Worker Logs Reverse Stream (RpcLog: Worker -> Host)

Each phase defines its own phase-specific Compound Topology edges (`topologyEdges`,
`activeNodes`, `bypassedNote`) AND its own Multi-Actor Sequence Diagram (`actors`, `steps`).
"""

from __future__ import annotations
from typing import Any


PHASE_CATALOG = [
    {"id": "init", "num": "1", "short": "Worker Init", "proto": "StartStream + WorkerInitRequest"},
    {"id": "specialization", "num": "2", "short": "Specialization", "proto": "FunctionEnvironmentReloadRequest"},
    {"id": "metadata", "num": "3", "short": "Metadata & Indexing", "proto": "FunctionsMetadataRequest"},
    {"id": "function_load", "num": "4", "short": "Functions Load (V1)", "proto": "FunctionLoadRequest"},
    {"id": "invocation", "num": "5", "short": "Invocation", "proto": "InvocationRequest"},
    {"id": "worker_status", "num": "6", "short": "Worker Status", "proto": "WorkerStatusRequest"},
    {"id": "worker_logs", "num": "7", "short": "Worker Logs", "proto": "RpcLog (Worker → Host)"},
]


def get_py312_phases() -> list[dict[str, Any]]:
    return [
        # 1. Worker Init
        {
            "id": "init",
            "title": "1. Worker Initialization Flow",
            "proto": "StartStream → WorkerInitRequest → WorkerInitResponse",
            "scope": "All SKUs (Cold Start)",
            "summary": (
                "Host spawns `prodV4/worker.py`, which boots `azure_functions_worker` with worker "
                "dependencies isolated first (`grpcio` + `protobuf`). Once `EventStream` connects and sends "
                "`StartStream`, `WorkerInitRequest` negotiates capabilities (`SHARED_MEMORY`, `RAW_HTTP_BODY_BYTES`, "
                "`WORKER_STATUS`), initializes OTel/AppInsights, promotes customer `.python_packages` (on Dedicated/EP), "
                "loads the binding registry, and optionally pre-indexes if `PYTHON_ENABLE_INIT_INDEXING=1`."
            ),
            "bypassedNote": "In Linux Consumption placeholder mode, customer packages are NOT mounted yet during Init (deferred to Phase 2 Specialization).",
            "activeNodes": ["n312-proto", "n312-boot", "n312-grpc", "n312-disp", "n312-dep", "n312-bind"],
            "topologyEdges": [
                {"id": "p312-i1", "source": "n312-proto", "target": "n312-boot", "kind": "syspath-mutation", "label": "1. spawn prodV4/worker.py"},
                {"id": "p312-i2", "source": "n312-boot", "target": "n312-grpc", "kind": "inproc-contract", "label": "2. use_worker_deps + connect()"},
                {"id": "p312-i3", "source": "n312-grpc", "target": "n312-proto", "kind": "grpc-wire", "label": "3. StartStream(worker_id)"},
                {"id": "p312-i4", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "4. WorkerInitRequest"},
                {"id": "p312-i5", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "5. call_soon_threadsafe"},
                {"id": "p312-i6", "source": "n312-disp", "target": "n312-dep", "kind": "syspath-mutation", "label": "6. prioritize_customer_deps()"},
                {"id": "p312-i7", "source": "n312-disp", "target": "n312-bind", "kind": "inproc-contract", "label": "7. load_binding_registry()"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "boot", "label": "prodV4 + main.py"},
                {"id": "grpc", "label": "gRPC Thread"},
                {"id": "disp", "label": "Monolith Dispatcher"},
                {"id": "dep", "label": "DependencyManager"},
            ],
            "steps": [
                {"from": "host", "to": "boot", "message": "Spawn python prodV4/worker.py --host --port --workerId", "payload": "DependencyManager.initialize() + use_worker_dependencies()", "activeNodes": ["n312-proto", "n312-boot"], "activeEdges": ["p312-i1"]},
                {"from": "boot", "to": "grpc", "message": "Dispatcher.connect() opens insecure grpcio channel", "payload": "Starts __poll_grpc background thread", "activeNodes": ["n312-boot", "n312-grpc"], "activeEdges": ["p312-i2"]},
                {"from": "grpc", "to": "host", "message": "Send StartStream(worker_id) + detach console logger", "isReturn": True, "payload": "Switches root logger to AsyncLoggingHandler", "activeNodes": ["n312-grpc", "n312-proto"], "activeEdges": ["p312-i3"]},
                {"from": "host", "to": "disp", "message": "WorkerInitRequest(capabilities, function_app_directory)", "payload": "Posted from gRPC thread to asyncio loop", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["p312-i4", "p312-i5"]},
                {"from": "disp", "to": "dep", "message": "should_load_cx_dependencies() -> prioritize_customer_deps()", "payload": "Dedicated: promotes customer .python_packages; Consumption: stays in placeholder", "activeNodes": ["n312-disp", "n312-dep"], "activeEdges": ["p312-i6"]},
                {"from": "disp", "to": "disp", "message": "Configure OTel/AppInsights + bindings.load_binding_registry()", "payload": "Optional load_function_metadata if PYTHON_ENABLE_INIT_INDEXING=1", "activeNodes": ["n312-disp", "n312-bind"], "activeEdges": ["p312-i7"]},
                {"from": "disp", "to": "host", "message": "WorkerInitResponse(capabilities, worker_metadata)", "isReturn": True, "payload": "SHARED_MEMORY_DATA_TRANSFER, WORKER_STATUS, RAW_HTTP_BODY_BYTES", "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["p312-i5", "p312-i3"]},
            ],
        },
        # 2. Worker Specialization
        {
            "id": "specialization",
            "title": "2. Worker Specialization Flow (Consumption Placeholder)",
            "proto": "FunctionEnvironmentReloadRequest → FunctionEnvironmentReloadResponse",
            "scope": "Linux / Flex Consumption Only (Placeholder Mode)",
            "summary": (
                "Warm standby containers boot before any customer app is assigned. When specialized, "
                "the Host mounts the customer package and sends `FunctionEnvironmentReloadRequest` carrying "
                "`function_app_directory` and `environment_variables`. The monolith clears `os.environ`, calls "
                "`time.tzset()`, clears `sys.path_importer_cache`, promotes customer `.python_packages`, recreates "
                "`_sync_call_tp` (`PYTHON_THREADPOOL_THREAD_COUNT`), and changes `cwd`."
            ),
            "bypassedNote": "Never sent on Dedicated/Premium cold boots or worker restarts (those go straight through WorkerInit).",
            "activeNodes": ["n312-proto", "n312-grpc", "n312-disp", "n312-dep", "n312-load", "n312-bind", "n312-sdk"],
            "topologyEdges": [
                {"id": "p312-s1", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "1. FunctionEnvironmentReloadRequest"},
                {"id": "p312-s2", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "2. _dispatch_grpc_request"},
                {"id": "p312-s3", "source": "n312-disp", "target": "n312-dep", "kind": "syspath-mutation", "label": "3. reload os.environ + sys.path"},
                {"id": "p312-s4", "source": "n312-dep", "target": "n312-sdk", "kind": "syspath-mutation", "label": "4. reload customer azure.functions", "dashed": True},
                {"id": "p312-s5", "source": "n312-disp", "target": "n312-load", "kind": "inproc-contract", "label": "5. optional init indexing + http_v2"},
                {"id": "p312-s6", "source": "n312-disp", "target": "n312-bind", "kind": "inproc-contract", "label": "6. recreate _sync_call_tp + bindings"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "disp", "label": "Monolith Dispatcher"},
                {"id": "dep", "label": "DependencyManager"},
                {"id": "sdk", "label": "Customer Packages"},
            ],
            "steps": [
                {"from": "host", "to": "disp", "message": "FunctionEnvironmentReloadRequest(app_dir, env_vars)", "payload": "Mounts /home/site/wwwroot into warm container", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["p312-s1", "p312-s2"]},
                {"from": "disp", "to": "disp", "message": "os.environ.clear() + apply env_vars + time.tzset()", "payload": "Recreates _sync_call_tp with customer PYTHON_THREADPOOL_THREAD_COUNT", "activeNodes": ["n312-disp", "n312-bind"], "activeEdges": ["p312-s6"]},
                {"from": "disp", "to": "dep", "message": "sys.path_importer_cache.clear() + prioritize_customer_deps()", "payload": "Evicts placeholder azure.functions so customer version loads", "activeNodes": ["n312-disp", "n312-dep", "n312-sdk"], "activeEdges": ["p312-s3", "p312-s4"]},
                {"from": "disp", "to": "disp", "message": "bindings.load_binding_registry() + os.chdir(app_dir)", "payload": "Initializes http_v2 server if streaming app", "activeNodes": ["n312-disp", "n312-load"], "activeEdges": ["p312-s5"]},
                {"from": "disp", "to": "host", "message": "FunctionEnvironmentReloadResponse(capabilities)", "isReturn": True, "payload": "Warm worker specialized & ready", "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["p312-s2", "p312-s1"]},
            ],
        },
        # 3. Metadata & Indexing
        {
            "id": "metadata",
            "title": "3. Worker Metadata & Indexing Flow",
            "proto": "FunctionsMetadataRequest → FunctionMetadataResponse",
            "scope": "V2 Worker-Indexed Apps (Returns Fallback Flag for V1)",
            "summary": (
                "Host asks the worker whether it owns function discovery. In `≤ 3.12`, `load_function_metadata()` "
                "checks if `function_app.py` exists: for **V2**, it imports `function_app.py`, walks `@app` "
                "decorators and `Blueprint`s (`python-library`) plus `WebApp`/`SdkType` hooks (`python-extensions`), "
                "and returns `RawFunctionMetadata` (`use_default_metadata_indexing=False`). For **V1**, it returns "
                "`use_default_metadata_indexing=True` so the Host scans `function.json` directories itself."
            ),
            "bypassedNote": "For V1 apps (`function.json`), no customer Python code is imported during Metadata — Host falls back to disk scanning.",
            "activeNodes": ["n312-proto", "n312-grpc", "n312-disp", "n312-load", "n312-sdk", "n312-ext"],
            "topologyEdges": [
                {"id": "p312-m1", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "1. FunctionsMetadataRequest"},
                {"id": "p312-m2", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "2. _handle__functions_metadata_request"},
                {"id": "p312-m3", "source": "n312-disp", "target": "n312-load", "kind": "inproc-contract", "label": "3. load_function_metadata()"},
                {"id": "p312-m4", "source": "n312-load", "target": "n312-sdk", "kind": "exec-dispatch", "label": "4a. V2: import function_app & @app"},
                {"id": "p312-m5", "source": "n312-load", "target": "n312-ext", "kind": "pyo3-control", "label": "4b. inspect WebApp / SdkType", "dashed": True},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "disp", "label": "Monolith Dispatcher"},
                {"id": "load", "label": "loader.py"},
                {"id": "sdk", "label": "python-library / App"},
            ],
            "steps": [
                {"from": "host", "to": "disp", "message": "FunctionsMetadataRequest(function_app_directory)", "payload": "Queries worker-indexed functions", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["p312-m1", "p312-m2"]},
                {"from": "disp", "to": "load", "message": "Check os.path.exists(function_app.py)", "payload": "PYTHON_SCRIPT_FILE_NAME (default function_app.py)", "activeNodes": ["n312-disp", "n312-load"], "activeEdges": ["p312-m3"]},
                {"from": "load", "to": "sdk", "message": "[V2] index_function_app() -> import function_app.py", "payload": "Extracts FunctionApp.get_functions() + Blueprints + triggers", "activeNodes": ["n312-load", "n312-sdk", "n312-ext"], "activeEdges": ["p312-m4", "p312-m5"]},
                {"from": "load", "to": "disp", "message": "Register FunctionInfo in _functions + build RawFunctionMetadata", "isReturn": True, "payload": "Or None if V1 app", "activeNodes": ["n312-load", "n312-disp"], "activeEdges": ["p312-m3"]},
                {"from": "disp", "to": "host", "message": "FunctionMetadataResponse(results, use_default_metadata_indexing)", "isReturn": True, "payload": "V2: False + metadata list | V1: True (Host scans function.json)", "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["p312-m2", "p312-m1"]},
            ],
        },
        # 4. Function Load (V1)
        {
            "id": "function_load",
            "title": "4. Worker Functions Load Flow (V1 Primary)",
            "proto": "FunctionLoadRequest → FunctionLoadResponse",
            "scope": "V1 Programming Model (`function.json`); V2 Multi-Worker / Ack",
            "summary": (
                "After the Host parses `function.json` files for a **V1** app, it sends one `FunctionLoadRequest` "
                "per function with `script_file`, `entry_point`, and `bindings`. `loader.load_function()` imports "
                "the target Python module (`__init__.py`), validates parameter type annotations against "
                "`bindings/`, and stores `FunctionInfo` in `self._functions`. (For V2 single-worker, `_functions` "
                "already holds the function from Phase 3, so it fast-acks; for 2nd+ workers in multi-proc mode, "
                "it triggers lazy V2 indexing)."
            ),
            "bypassedNote": "For standard V2 apps, user scripts were already loaded in Phase 3 Metadata, making FunctionLoad a fast registry check.",
            "activeNodes": ["n312-proto", "n312-grpc", "n312-disp", "n312-load", "n312-bind", "n312-sdk"],
            "topologyEdges": [
                {"id": "p312-l1", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "1. FunctionLoadRequest(metadata)"},
                {"id": "p312-l2", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "2. _handle__function_load_request"},
                {"id": "p312-l3", "source": "n312-disp", "target": "n312-load", "kind": "inproc-contract", "label": "3. loader.load_function(script_file)"},
                {"id": "p312-l4", "source": "n312-load", "target": "n312-sdk", "kind": "exec-dispatch", "label": "4. importlib import __init__.py"},
                {"id": "p312-l5", "source": "n312-disp", "target": "n312-bind", "kind": "inproc-contract", "label": "5. validate binding types & add_function"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "disp", "label": "Monolith Dispatcher"},
                {"id": "load", "label": "loader.py"},
                {"id": "app", "label": "V1 __init__.py"},
            ],
            "steps": [
                {"from": "host", "to": "disp", "message": "FunctionLoadRequest(function_id, RpcFunctionMetadata)", "payload": "Carries script_file, entry_point, and function.json bindings", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["p312-l1", "p312-l2"]},
                {"from": "disp", "to": "load", "message": "loader.load_function(name, dir, script_file, entry_point)", "payload": "Only runs when function_id not yet in _functions (V1)", "activeNodes": ["n312-disp", "n312-load"], "activeEdges": ["p312-l3"]},
                {"from": "load", "to": "app", "message": "importlib.import_module() -> resolve main() callable", "payload": "Executes module top-level imports", "activeNodes": ["n312-load", "n312-sdk"], "activeEdges": ["p312-l4"]},
                {"from": "disp", "to": "disp", "message": "_functions.add_function(function_id, func, metadata)", "payload": "Validates Python type hints vsIn/Out binding converters", "activeNodes": ["n312-disp", "n312-bind"], "activeEdges": ["p312-l5"]},
                {"from": "disp", "to": "host", "message": "FunctionLoadResponse(function_id, Success)", "isReturn": True, "payload": "Function ready to invoke", "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["p312-l2", "p312-l1"]},
            ],
        },
        # 5. Invocation
        {
            "id": "invocation",
            "title": "5. Worker Invocation Flow",
            "proto": "InvocationRequest → InvocationResponse",
            "scope": "Every Function Trigger Execution",
            "summary": (
                "Host sends `InvocationRequest` with `input_data` (`TypedData` or POSIX/Win shared-memory map) "
                "and `trigger_metadata`. `Dispatcher` decodes bindings via `python-library` (`Datum`) or "
                "`python-extensions` (`SdkType` / `http_v2`), sets W3C OpenTelemetry context, executes `async def` "
                "on the event loop or `def` on `_sync_call_tp`, and marshals `Out[T]` + `$return` back to protobuf."
            ),
            "bypassedNote": "`prodV4` boot and `loader.py` are idle during steady-state invocations.",
            "activeNodes": ["n312-proto", "n312-grpc", "n312-disp", "n312-bind", "n312-sdk", "n312-ext"],
            "topologyEdges": [
                {"id": "p312-v1", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "1. InvocationRequest"},
                {"id": "p312-v2", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "2. call_soon_threadsafe"},
                {"id": "p312-v3", "source": "n312-disp", "target": "n312-bind", "kind": "inproc-contract", "label": "3. from_incoming_proto / ShMem"},
                {"id": "p312-v4", "source": "n312-bind", "target": "n312-ext", "kind": "pyo3-control", "label": "4a. http_v2 / SdkType", "dashed": True},
                {"id": "p312-v5", "source": "n312-bind", "target": "n312-sdk", "kind": "exec-dispatch", "label": "4b. await / _sync_call_tp"},
                {"id": "p312-v6", "source": "n312-disp", "target": "n312-grpc", "kind": "thread-queue", "label": "5. _grpc_resp_queue.put"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "disp", "label": "Monolith Dispatcher"},
                {"id": "bind", "label": "Bindings / SharedMem"},
                {"id": "app", "label": "SDK & User Handler"},
            ],
            "steps": [
                {"from": "host", "to": "disp", "message": "InvocationRequest(invocation_id, function_id, input_data)", "payload": "google.protobuf StreamingMessage", "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"], "activeEdges": ["p312-v1", "p312-v2"]},
                {"from": "disp", "to": "bind", "message": "from_incoming_proto() + get_context() + OTel traceparent", "payload": "Reads TypedData or SharedMemoryManager buffer", "activeNodes": ["n312-disp", "n312-bind"], "activeEdges": ["p312-v3"]},
                {"from": "bind", "to": "app", "message": "Execute async coroutine or run_in_executor(_sync_call_tp)", "payload": "Runs ExtensionManager pre/post invocation hooks", "activeNodes": ["n312-bind", "n312-sdk", "n312-ext"], "activeEdges": ["p312-v4", "p312-v5"]},
                {"from": "app", "to": "disp", "message": "to_outgoing_proto($return, Out) + sys.stdout.flush()", "isReturn": True, "payload": "Builds protos.InvocationResponse", "activeNodes": ["n312-sdk", "n312-bind", "n312-disp"], "activeEdges": ["p312-v5", "p312-v3"]},
                {"from": "disp", "to": "host", "message": "Enqueue StreamingMessage(invocation_response)", "isReturn": True, "payload": "Sent over grpcio EventStream", "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["p312-v6", "p312-v1"]},
            ],
        },
        # 6. Worker Status
        {
            "id": "worker_status",
            "title": "6. Worker Status Flow (Host Health & Scale Probe)",
            "proto": "WorkerStatusRequest → WorkerStatusResponse",
            "scope": "Host Scale Controller & Worker Health Monitoring",
            "summary": (
                "The Host periodically sends `WorkerStatusRequest` to measure worker round-trip responsiveness "
                "for out-of-proc scaling decisions. In `≤ 3.12`, `_handle__worker_status_request` suppresses "
                "all logging and returns an empty `WorkerStatusResponse` immediately—**however**, it still "
                "hop-schedules onto the single Python `asyncio` event loop and acquires the GIL."
            ),
            "bypassedNote": "Loader, Bindings, SDK, Extensions, and User Code are completely untouched — pure transport/loop health probe.",
            "activeNodes": ["n312-proto", "n312-grpc", "n312-disp"],
            "topologyEdges": [
                {"id": "p312-st1", "source": "n312-proto", "target": "n312-grpc", "kind": "grpc-wire", "label": "1. WorkerStatusRequest"},
                {"id": "p312-st2", "source": "n312-grpc", "target": "n312-disp", "kind": "thread-queue", "label": "2. call_soon_threadsafe (GIL + loop)"},
                {"id": "p312-st3", "source": "n312-disp", "target": "n312-grpc", "kind": "thread-queue", "label": "3. WorkerStatusResponse (no logs)"},
                {"id": "p312-st4", "source": "n312-grpc", "target": "n312-proto", "kind": "grpc-wire", "label": "4. EventStream reply"},
            ],
            "actors": [
                {"id": "host", "label": "Host Scale Controller"},
                {"id": "grpc", "label": "gRPC Thread"},
                {"id": "disp", "label": "Dispatcher (asyncio)"},
            ],
            "steps": [
                {"from": "host", "to": "grpc", "message": "WorkerStatusRequest(request_id)", "payload": "Probes worker event-loop latency", "activeNodes": ["n312-proto", "n312-grpc"], "activeEdges": ["p312-st1"]},
                {"from": "grpc", "to": "disp", "message": "call_soon_threadsafe(_handle__worker_status_request)", "payload": "Warning: blocked user event loop delays status reply!", "activeNodes": ["n312-grpc", "n312-disp"], "activeEdges": ["p312-st2"]},
                {"from": "disp", "to": "host", "message": "WorkerStatusResponse() via _grpc_resp_queue", "isReturn": True, "payload": "Logging suppressed to avoid I/O overhead", "activeNodes": ["n312-disp", "n312-grpc", "n312-proto"], "activeEdges": ["p312-st3", "p312-st4"]},
            ],
        },
        # 7. Worker Logs
        {
            "id": "worker_logs",
            "title": "7. Worker Logs Flow (Worker → Host Reverse Stream)",
            "proto": "Python logging.LogRecord → StreamingMessage(RpcLog) → Host",
            "scope": "Reverse Telemetry Stream (System & Customer Logs)",
            "summary": (
                "Before `EventStream` connects, logs print to stdout/stderr with prefix `LanguageWorkerConsoleLog`. "
                "Once connected, `disable_console_logging()` detaches console output and attaches `AsyncLoggingHandler` "
                "to the root logger. Every `logging.info/error` from customer code (`User` category) or worker "
                "(`System` category) is stamped with `invocation_id` (from task/thread-local) and pushed **back "
                "to the Host** on `_grpc_resp_queue` as `RpcLog` messages for Application Insights & Kusto."
            ),
            "bypassedNote": "Originates inside User Code or Worker internals and flows RIGHT → LEFT back to the Host without a Host request.",
            "activeNodes": ["n312-sdk", "n312-disp", "n312-grpc", "n312-proto"],
            "topologyEdges": [
                {"id": "p312-lg1", "source": "n312-sdk", "target": "n312-disp", "kind": "pyo3-control", "label": "1. logging.info() -> AsyncLoggingHandler"},
                {"id": "p312-lg2", "source": "n312-disp", "target": "n312-grpc", "kind": "thread-queue", "label": "2. stamp invocation_id -> _grpc_resp_queue"},
                {"id": "p312-lg3", "source": "n312-grpc", "target": "n312-proto", "kind": "grpc-wire", "label": "3. StreamingMessage(rpc_log) → Host"},
            ],
            "actors": [
                {"id": "app", "label": "User Code / Worker"},
                {"id": "disp", "label": "AsyncLoggingHandler"},
                {"id": "grpc", "label": "_grpc_resp_queue"},
                {"id": "host", "label": "Host (AppInsights / Kusto)"},
            ],
            "steps": [
                {"from": "app", "to": "disp", "message": "logging.info('Order processed') / logger.info(...)", "payload": "Captured by root logger AsyncLoggingHandler", "activeNodes": ["n312-sdk", "n312-disp"], "activeEdges": ["p312-lg1"]},
                {"from": "disp", "to": "disp", "message": "Classify System vs User + resolve invocation_id", "payload": "Checks current asyncio task / thread_local_storage.invocation_id", "activeNodes": ["n312-disp"], "activeEdges": []},
                {"from": "disp", "to": "grpc", "message": "put_nowait(StreamingMessage(rpc_log=RpcLog(...)))", "payload": "Non-blocking enqueue onto outbound gRPC queue", "activeNodes": ["n312-disp", "n312-grpc"], "activeEdges": ["p312-lg2"]},
                {"from": "grpc", "to": "host", "message": "Stream RpcLog frame over EventStream to Host", "isReturn": True, "payload": "User logs -> Customer AppInsights | System logs -> Kusto", "activeNodes": ["n312-grpc", "n312-proto"], "activeEdges": ["p312-lg3"]},
            ],
        },
    ]


def get_py313_phases() -> list[dict[str, Any]]:
    return [
        # 1. Worker Init
        {
            "id": "init",
            "title": "1. Worker Initialization Flow (Runtime Selection + V2 Default Indexing)",
            "proto": "StartStream → WorkerInitRequest → WorkerRequest(protos) → WorkerInitResponse",
            "scope": "All SKUs (Cold Start)",
            "summary": (
                "`proxyV4/worker.py` starts `proxy_worker` with `uvloop` and worker-first deps (`grpcio`/`protobuf`). "
                "On `WorkerInitRequest`, `proxy_worker` promotes customer deps, runs **`reload_library_worker(dir)`** "
                "(resolving `PYTHON_ENABLE_AGENT_RUNTIME` `entry_points` → `function_app.py` V2 → V1), starts the "
                "runtime threadpool, and passes `WorkerRequest(properties={'protos': protos, 'host': host})`. "
                "**Key change in 3.13+**: Runtime V2 now **indexes `function_app.py` and starts `http_v2` during `WorkerInit`**!"
            ),
            "bypassedNote": "Only ONE runtime engine (Agent, V2, or V1) is imported and bound to `_library_worker`.",
            "activeNodes": ["n313-proto", "n313-grpc", "n313-router", "n313-rtv2", "n313-rtv1", "n313-ext", "n313-lib"],
            "topologyEdges": [
                {"id": "p313-i1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "1. StartStream + WorkerInitRequest"},
                {"id": "p313-i2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "2. call_soon_threadsafe"},
                {"id": "p313-i3", "source": "n313-router", "target": "n313-ext", "kind": "syspath-mutation", "label": "3a. check Agent Runtime entry_points", "dashed": True},
                {"id": "p313-i4", "source": "n313-router", "target": "n313-rtv2", "kind": "inproc-contract", "label": "3b. V2: WorkerRequest(protos, host)"},
                {"id": "p313-i5", "source": "n313-router", "target": "n313-rtv1", "kind": "inproc-contract", "label": "3c. V1: WorkerRequest(protos, host)", "dashed": True},
                {"id": "p313-i6", "source": "n313-rtv2", "target": "n313-lib", "kind": "exec-dispatch", "label": "4. V2 indexes function_app.py in Init!"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "proxy", "label": "proxy_worker"},
                {"id": "ext", "label": "python-extensions"},
                {"id": "rt", "label": "Runtime (v2 / v1)"},
                {"id": "lib", "label": "python-library / App"},
            ],
            "steps": [
                {"from": "host", "to": "proxy", "message": "Spawn proxyV4 -> start_worker(uvloop) + StartStream", "payload": "use_worker_dependencies() protects grpcio import", "activeNodes": ["n313-proto", "n313-grpc"], "activeEdges": ["p313-i1"]},
                {"from": "host", "to": "proxy", "message": "WorkerInitRequest(function_app_directory)", "payload": "prioritize_customer_dependencies() if Dedicated", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["p313-i1", "p313-i2"]},
                {"from": "proxy", "to": "ext", "message": "reload_library_worker(): check AGENT_RUNTIME entry_points", "payload": "RuntimeTrackerMeta -> else function_app.py (V2) -> else V1", "activeNodes": ["n313-router", "n313-ext"], "activeEdges": ["p313-i3"]},
                {"from": "proxy", "to": "rt", "message": "start_threadpool_executor() + worker_init_request(WorkerRequest)", "payload": "Injects properties={'protos': protos, 'host': host}", "activeNodes": ["n313-router", "n313-rtv2", "n313-rtv1"], "activeEdges": ["p313-i4", "p313-i5"]},
                {"from": "rt", "to": "lib", "message": "[V2] Cache protos, load_binding_registry, index_function_app()", "payload": "V2 indexes in Init & starts http_v2 server; V1 only runs install()", "activeNodes": ["n313-rtv2", "n313-lib"], "activeEdges": ["p313-i6"]},
                {"from": "rt", "to": "host", "message": "WorkerInitResponse -> wrapped in StreamingMessage", "isReturn": True, "payload": "Capabilities + PyPI runtime version metadata", "activeNodes": ["n313-rtv2", "n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-i4", "p313-i2", "p313-i1"]},
            ],
        },
        # 2. Worker Specialization
        {
            "id": "specialization",
            "title": "2. Worker Specialization Flow (Consumption Runtime Swap)",
            "proto": "FunctionEnvironmentReloadRequest → reload_library_worker() → ReloadResponse",
            "scope": "Linux / Flex Consumption Only (Placeholder Mode)",
            "summary": (
                "During placeholder boot, the worker defaulted to bundled `azure_functions_runtime`. On "
                "`FunctionEnvironmentReloadRequest`, `proxy_worker` promotes the newly mounted customer `.python_packages`, "
                "**re-runs `reload_library_worker(directory)`** (so a V1 app switches to `azure_functions_runtime_v1`, "
                "an Agent app loads its custom runtime, or a customer-pinned PyPI `azure-functions-runtime` takes over!), "
                "re-injects `protos`, reloads `os.environ` + `tzset()`, and indexes the specialized app."
            ),
            "bypassedNote": "Only occurs when specializing warm Consumption standby containers.",
            "activeNodes": ["n313-proto", "n313-grpc", "n313-router", "n313-rtv2", "n313-rtv1", "n313-ext", "n313-lib"],
            "topologyEdges": [
                {"id": "p313-s1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "1. FunctionEnvironmentReloadRequest"},
                {"id": "p313-s2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "2. prioritize_customer_deps(dir)"},
                {"id": "p313-s3", "source": "n313-router", "target": "n313-ext", "kind": "syspath-mutation", "label": "3a. re-evaluate Agent Runtime", "dashed": True},
                {"id": "p313-s4", "source": "n313-router", "target": "n313-rtv2", "kind": "inproc-contract", "label": "3b. reload V2 + inject protos"},
                {"id": "p313-s5", "source": "n313-router", "target": "n313-rtv1", "kind": "inproc-contract", "label": "3c. or switch to V1!", "dashed": True},
                {"id": "p313-s6", "source": "n313-rtv2", "target": "n313-lib", "kind": "exec-dispatch", "label": "4. reset_host_config + env + index"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "proxy", "label": "proxy_worker"},
                {"id": "rt", "label": "Selected Runtime"},
                {"id": "lib", "label": "Customer Env & App"},
            ],
            "steps": [
                {"from": "host", "to": "proxy", "message": "FunctionEnvironmentReloadRequest(app_dir, env_vars)", "payload": "Specializes warm placeholder container", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["p313-s1", "p313-s2"]},
                {"from": "proxy", "to": "proxy", "message": "DependencyManager.prioritize_customer_dependencies(dir)", "payload": "Evicts worker runtime modules so customer PyPI pin can win", "activeNodes": ["n313-router"], "activeEdges": []},
                {"from": "proxy", "to": "rt", "message": "reload_library_worker(dir) + start_threadpool_executor()", "payload": "Dynamically switches _library_worker to Agent / V2 / V1", "activeNodes": ["n313-router", "n313-ext", "n313-rtv2", "n313-rtv1"], "activeEdges": ["p313-s3", "p313-s4", "p313-s5"]},
                {"from": "rt", "to": "lib", "message": "function_environment_reload_request(WorkerRequest(protos))", "payload": "Reloads os.environ, tzset(), OTel, http_v2, change_cwd, and indexes V2", "activeNodes": ["n313-rtv2", "n313-lib"], "activeEdges": ["p313-s6"]},
                {"from": "rt", "to": "host", "message": "FunctionEnvironmentReloadResponse(capabilities)", "isReturn": True, "payload": "Specialized container ready", "activeNodes": ["n313-rtv2", "n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-s4", "p313-s2", "p313-s1"]},
            ],
        },
        # 3. Metadata & Indexing
        {
            "id": "metadata",
            "title": "3. Worker Metadata Flow (Cached V2 Result vs V1 Host Fallback)",
            "proto": "FunctionsMetadataRequest → WorkerRequest → FunctionMetadataResponse",
            "scope": "V2 Returns Cached Metadata; V1 Delegates Indexing to Host",
            "summary": (
                "`proxy_worker` forwards `WorkerRequest(name='WorkerMetadataRequest')` (no `protos` needed — "
                "already cached in runtime!). In **Runtime V2**, `functions_metadata_request` immediately returns "
                "the `_metadata_result` indexed during Init/Specialization (`use_default_metadata_indexing=False`). "
                "In **Runtime V1**, it returns `use_default_metadata_indexing=True, results=None` so the Host "
                "reads `function.json` files."
            ),
            "bypassedNote": "V2 already indexed `function_app.py` during Init/Specialization, so Phase 3 is an O(1) cached return!",
            "activeNodes": ["n313-proto", "n313-grpc", "n313-router", "n313-rtv2", "n313-rtv1"],
            "topologyEdges": [
                {"id": "p313-m1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "1. FunctionsMetadataRequest"},
                {"id": "p313-m2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "2. _handle__functions_metadata_request"},
                {"id": "p313-m3", "source": "n313-router", "target": "n313-rtv2", "kind": "inproc-contract", "label": "3a. V2: return cached _metadata_result"},
                {"id": "p313-m4", "source": "n313-router", "target": "n313-rtv1", "kind": "inproc-contract", "label": "3b. V1: use_default_indexing=True", "dashed": True},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "proxy", "label": "proxy_worker"},
                {"id": "rtv2", "label": "Runtime V2"},
                {"id": "rtv1", "label": "Runtime V1"},
            ],
            "steps": [
                {"from": "host", "to": "proxy", "message": "FunctionsMetadataRequest(function_app_directory)", "payload": "Requests function list", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["p313-m1", "p313-m2"]},
                {"from": "proxy", "to": "rtv2", "message": "[If V2] await rtv2.functions_metadata_request(req)", "payload": "Returns pre-indexed _metadata_result (use_default=False)", "activeNodes": ["n313-router", "n313-rtv2"], "activeEdges": ["p313-m3"]},
                {"from": "proxy", "to": "rtv1", "message": "[If V1] await rtv1.functions_metadata_request(req)", "payload": "Returns None + use_default_metadata_indexing=True", "activeNodes": ["n313-router", "n313-rtv1"], "activeEdges": ["p313-m4"]},
                {"from": "proxy", "to": "host", "message": "StreamingMessage(function_metadata_response)", "isReturn": True, "payload": "Host registers V2 functions or scans V1 function.json", "activeNodes": ["n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-m2", "p313-m1"]},
            ],
        },
        # 4. Function Load (V1)
        {
            "id": "function_load",
            "title": "4. Worker Functions Load Flow (V1 Script Loading vs V2 No-Op)",
            "proto": "FunctionLoadRequest → WorkerRequest → FunctionLoadResponse",
            "scope": "Active Import for V1 (`runtimes/v1`); Immediate No-Op Ack for V2",
            "summary": (
                "The split makes V1 vs V2 load behavior explicit: **`runtimes/v1/handle_event.py`** implements "
                "real `load_function()` + `_functions.add_function(function_id, func, metadata, protos)` to import "
                "each `function.json` script; **`runtimes/v2/handle_event.py`** (`L160`) is a 6-line immediate "
                "`FunctionLoadResponse(Success)` because V2 functions were already loaded during indexing!"
            ),
            "bypassedNote": "In Runtime V2, `function_load_request` is a pure no-op acknowledgment.",
            "activeNodes": ["n313-proto", "n313-grpc", "n313-router", "n313-rtv1", "n313-rtv2", "n313-lib"],
            "topologyEdges": [
                {"id": "p313-l1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "1. FunctionLoadRequest"},
                {"id": "p313-l2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "2. WorkerRequest"},
                {"id": "p313-l3", "source": "n313-router", "target": "n313-rtv1", "kind": "inproc-contract", "label": "3a. V1: load_function + add_function"},
                {"id": "p313-l4", "source": "n313-rtv1", "target": "n313-lib", "kind": "exec-dispatch", "label": "4. V1 imports __init__.py & SDK hints"},
                {"id": "p313-l5", "source": "n313-router", "target": "n313-rtv2", "kind": "inproc-contract", "label": "3b. V2: immediate Success ack", "dashed": True},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "proxy", "label": "proxy_worker"},
                {"id": "rtv1", "label": "Runtime V1"},
                {"id": "app", "label": "V1 __init__.py"},
            ],
            "steps": [
                {"from": "host", "to": "proxy", "message": "FunctionLoadRequest(function_id, metadata)", "payload": "Sent per function", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["p313-l1", "p313-l2"]},
                {"from": "proxy", "to": "rtv1", "message": "[V1] await rtv1.function_load_request(WorkerRequest)", "payload": "(In V2, rtv2 immediately returns Success no-op)", "activeNodes": ["n313-router", "n313-rtv1", "n313-rtv2"], "activeEdges": ["p313-l3", "p313-l5"]},
                {"from": "rtv1", "to": "app", "message": "loader.load_function() imports script_file & entry_point", "payload": "_functions.add_function(id, func, metadata, protos)", "activeNodes": ["n313-rtv1", "n313-lib"], "activeEdges": ["p313-l4"]},
                {"from": "rtv1", "to": "host", "message": "FunctionLoadResponse(function_id, Success)", "isReturn": True, "payload": "Wrapped in StreamingMessage by proxy_worker", "activeNodes": ["n313-rtv1", "n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-l3", "p313-l2", "p313-l1"]},
            ],
        },
        # 5. Invocation
        {
            "id": "invocation",
            "title": "5. Worker Invocation Flow",
            "proto": "InvocationRequest → WorkerRequest → Runtime v2/v1 → InvocationResponse",
            "scope": "Every Function Trigger Execution",
            "summary": (
                "`proxy_worker` stamps the `ContextEnabledTask` with `invocation_id` and awaits "
                "`_library_worker.invocation_request(WorkerRequest)`. The runtime decodes inputs using its "
                "cached `protos`, coordinates `http_v2` streaming or `SdkType` bindings (`python-extensions`), "
                "executes async on `uvloop` or sync on the runtime's `ThreadPoolExecutor`, and returns `InvocationResponse`."
            ),
            "bypassedNote": "Runtime discovery and `protos` injection do NOT run per-invocation — cached from Phase 1/2.",
            "activeNodes": ["n313-proto", "n313-grpc", "n313-router", "n313-rtv2", "n313-ext", "n313-lib"],
            "topologyEdges": [
                {"id": "p313-v1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "1. InvocationRequest"},
                {"id": "p313-v2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "2. ContextEnabledTask"},
                {"id": "p313-v3", "source": "n313-router", "target": "n313-rtv2", "kind": "inproc-contract", "label": "3. WorkerRequest (no protos copy)"},
                {"id": "p313-v4", "source": "n313-rtv2", "target": "n313-ext", "kind": "pyo3-control", "label": "4a. http_v2 / SdkType / Settlement", "dashed": True},
                {"id": "p313-v5", "source": "n313-rtv2", "target": "n313-lib", "kind": "exec-dispatch", "label": "4b. execute_async / run_sync_func"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "proxy", "label": "proxy_worker"},
                {"id": "rt", "label": "Runtime Engine"},
                {"id": "app", "label": "SDK / Extensions / App"},
            ],
            "steps": [
                {"from": "host", "to": "proxy", "message": "InvocationRequest(invocation_id, function_id)", "payload": "Dispatched onto ContextEnabledTask", "activeNodes": ["n313-proto", "n313-grpc", "n313-router"], "activeEdges": ["p313-v1", "p313-v2"]},
                {"from": "proxy", "to": "rt", "message": "await _library_worker.invocation_request(WorkerRequest)", "payload": "Stamps global/task invocation_id before call", "activeNodes": ["n313-router", "n313-rtv2"], "activeEdges": ["p313-v3"]},
                {"from": "rt", "to": "app", "message": "from_incoming_proto -> http_v2/SdkType -> run handler", "payload": "invocation_id_cv set on contextvar + threadpool thread", "activeNodes": ["n313-rtv2", "n313-ext", "n313-lib"], "activeEdges": ["p313-v4", "p313-v5"]},
                {"from": "app", "to": "host", "message": "to_outgoing_proto -> InvocationResponse -> _grpc_resp_queue", "isReturn": True, "payload": "StreamingMessage sent over grpcio", "activeNodes": ["n313-lib", "n313-rtv2", "n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-v5", "p313-v3", "p313-v2", "p313-v1"]},
            ],
        },
        # 6. Worker Status
        {
            "id": "worker_status",
            "title": "6. Worker Status Flow (Proxy Short-Circuit)",
            "proto": "WorkerStatusRequest → proxy_worker → WorkerStatusResponse",
            "scope": "Host Scale Controller Health Check (Runtime Bypassed!)",
            "summary": (
                "In `3.13 – 3.14`, `_handle__worker_status_request` is the **only** message handler in "
                "`proxy_worker/dispatcher.py` that **does NOT delegate to `_library_worker`**! It short-circuits "
                "inside `proxy_worker` and returns `WorkerStatusResponse` immediately—though it still runs on "
                "the shared CPython interpreter's `uvloop` and GIL."
            ),
            "bypassedNote": "Runtime V2, Runtime V1, SDK, Extensions, and Customer App are 100% bypassed!",
            "activeNodes": ["n313-proto", "n313-grpc", "n313-router"],
            "topologyEdges": [
                {"id": "p313-st1", "source": "n313-proto", "target": "n313-grpc", "kind": "grpc-wire", "label": "1. WorkerStatusRequest"},
                {"id": "p313-st2", "source": "n313-grpc", "target": "n313-router", "kind": "thread-queue", "label": "2. proxy short-circuit (still GIL)"},
                {"id": "p313-st3", "source": "n313-router", "target": "n313-grpc", "kind": "thread-queue", "label": "3. WorkerStatusResponse"},
                {"id": "p313-st4", "source": "n313-grpc", "target": "n313-proto", "kind": "grpc-wire", "label": "4. EventStream reply"},
            ],
            "actors": [
                {"id": "host", "label": "Host Scale Controller"},
                {"id": "grpc", "label": "Proxy gRPC Thread"},
                {"id": "proxy", "label": "Proxy Dispatcher"},
            ],
            "steps": [
                {"from": "host", "to": "grpc", "message": "WorkerStatusRequest()", "payload": "Scale controller health check", "activeNodes": ["n313-proto", "n313-grpc"], "activeEdges": ["p313-st1"]},
                {"from": "grpc", "to": "proxy", "message": "_handle__worker_status_request (short-circuit)", "payload": "Never crosses WorkerRequest seam; still requires Python GIL/loop", "activeNodes": ["n313-grpc", "n313-router"], "activeEdges": ["p313-st2"]},
                {"from": "proxy", "to": "host", "message": "WorkerStatusResponse()", "isReturn": True, "payload": "Returned via _grpc_resp_queue", "activeNodes": ["n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-st3", "p313-st4"]},
            ],
        },
        # 7. Worker Logs
        {
            "id": "worker_logs",
            "title": "7. Worker Logs Flow (4-Tier Invocation-ID Correlation → Host)",
            "proto": "LogRecord → 4-Tier ID Resolver → StreamingMessage(RpcLog) → Host",
            "scope": "Reverse Telemetry Stream (Worker / Runtime / Customer → Host)",
            "summary": (
                "Because execution lives in a separate PyPI runtime package (or custom Agent Runtime), "
                "`proxy_worker`'s `AsyncLoggingHandler` resolves `invocation_id` across **4 fallback tiers**: "
                "1) global tracker (for custom runtimes without `cv`), 2) `ContextEnabledTask` attribute, "
                "3) `_library_worker.invocation_id_cv` (`ContextVar`), and 4) `_thread_invocation_registry`—then "
                "streams `RpcLog` frames back to the Host."
            ),
            "bypassedNote": "Flows RIGHT → LEFT from User App / Runtime loggers through proxy_worker's AsyncLoggingHandler to the Host.",
            "activeNodes": ["n313-lib", "n313-rtv2", "n313-router", "n313-grpc", "n313-proto"],
            "topologyEdges": [
                {"id": "p313-lg1", "source": "n313-lib", "target": "n313-rtv2", "kind": "exec-dispatch", "label": "1. user logging.info() (cv / TLS set)"},
                {"id": "p313-lg2", "source": "n313-rtv2", "target": "n313-router", "kind": "pyo3-control", "label": "2. root AsyncLoggingHandler + 4-tier ID"},
                {"id": "p313-lg3", "source": "n313-router", "target": "n313-grpc", "kind": "thread-queue", "label": "3. protos.RpcLog -> _grpc_resp_queue"},
                {"id": "p313-lg4", "source": "n313-grpc", "target": "n313-proto", "kind": "grpc-wire", "label": "4. StreamingMessage(rpc_log) → Host"},
            ],
            "actors": [
                {"id": "app", "label": "User Code / Thread"},
                {"id": "rt", "label": "Runtime (invocation_id_cv)"},
                {"id": "proxy", "label": "Proxy AsyncLoggingHandler"},
                {"id": "host", "label": "Host (AppInsights / Kusto)"},
            ],
            "steps": [
                {"from": "app", "to": "proxy", "message": "logging.info(...) from async task, threadpool, or user thread", "payload": "Triggers root logger AsyncLoggingHandler in proxy_worker", "activeNodes": ["n313-lib", "n313-rtv2", "n313-router"], "activeEdges": ["p313-lg1", "p313-lg2"]},
                {"from": "proxy", "to": "rt", "message": "get_current_invocation_id() 4-tier lookup", "payload": "Global -> ContextEnabledTask -> runtime.invocation_id_cv -> thread registry", "activeNodes": ["n313-router", "n313-rtv2"], "activeEdges": ["p313-lg2"]},
                {"from": "proxy", "to": "host", "message": "Tag System vs User -> protos.RpcLog -> EventStream", "isReturn": True, "payload": "Correlated by invocation_id in Application Insights", "activeNodes": ["n313-router", "n313-grpc", "n313-proto"], "activeEdges": ["p313-lg3", "p313-lg4"]},
            ],
        },
    ]


def get_py315_phases() -> list[dict[str, Any]]:
    return [
        # 1. Worker Init
        {
            "id": "init",
            "title": "1. Worker Initialization Flow (Embed CPython + Protobuf-Free Init)",
            "proto": "bridge::configure → StartStream (prost) → WorkerInitRequest → protos_adapter",
            "scope": "All SKUs (Cold Start)",
            "summary": (
                "Host spawns compiled Rust binary `r2p2`. Before dialing gRPC, `main.rs` creates a single lock-free "
                "`tokio::mpsc::unbounded_channel<Bytes>` and calls `bridge::configure()` via PyO3 (embedding CPython, "
                "starting `bridge-asyncio` loop thread, and attaching `_RpcLogHandler` to Rust's `LogSink`). "
                "Rust opens `tonic` `EventStream`, sends `prost`-encoded `StartStream`, and routes `WorkerInitRequest` "
                "as a `PyDict` through `bridge.py` + pure-Python `protos_adapter.py` into Runtime V2/V1."
            ),
            "bypassedNote": "Hot FFI (`convert.rs` / `native_invocation.py`) is not used during control-plane initialization.",
            "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi", "n315-bridge-py", "n315-rt", "n315-lib"],
            "topologyEdges": [
                {"id": "p315-i1", "source": "n315-tonic", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "1. bridge::configure(LogSink)"},
                {"id": "p315-i2", "source": "n315-tonic", "target": "n315-proto", "kind": "grpc-wire", "label": "2. tonic connect + StartStream (prost)"},
                {"id": "p315-i3", "source": "n315-proto", "target": "n315-router", "kind": "grpc-wire", "label": "3. WorkerInitRequest bytes"},
                {"id": "p315-i4", "source": "n315-router", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "4. worker_init_req_to_py(PyDict)"},
                {"id": "p315-i5", "source": "n315-ctrl-ffi", "target": "n315-bridge-py", "kind": "pyo3-control", "label": "5. handle_control + select v2/v1"},
                {"id": "p315-i6", "source": "n315-bridge-py", "target": "n315-rt", "kind": "inproc-contract", "label": "6. WorkerRequest(protos=protos_adapter)"},
                {"id": "p315-i7", "source": "n315-rt", "target": "n315-lib", "kind": "exec-dispatch", "label": "7. V2 indexes @app decorators"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "rust", "label": "R2P2 (tonic+prost)"},
                {"id": "ctrl", "label": "bridge.rs (PyO3)"},
                {"id": "bpy", "label": "bridge.py + adapter"},
                {"id": "rt", "label": "Runtime v2 / v1"},
            ],
            "steps": [
                {"from": "rust", "to": "bpy", "message": "Create mpsc<Bytes> + bridge::configure(LogSink)", "payload": "Embeds libpython3.15, starts bridge-asyncio thread, installs _RpcLogHandler", "activeNodes": ["n315-tonic", "n315-ctrl-ffi", "n315-bridge-py"], "activeEdges": ["p315-i1", "p315-i5"]},
                {"from": "rust", "to": "host", "message": "Dial tonic EventStream + send prost StartStream(worker_id)", "isReturn": True, "payload": "BytesCodec over HTTP/2 TCP_NODELAY", "activeNodes": ["n315-tonic", "n315-proto"], "activeEdges": ["p315-i2"]},
                {"from": "host", "to": "ctrl", "message": "WorkerInitRequest -> prost decode -> worker_init_req_to_py", "payload": "Zero google.protobuf in Python!", "activeNodes": ["n315-proto", "n315-router", "n315-ctrl-ffi"], "activeEdges": ["p315-i3", "p315-i4"]},
                {"from": "ctrl", "to": "bpy", "message": "bridge.handle_control('worker_init_request', dict)", "payload": "_prioritize_customer_dependencies + _select_runtime(dir)", "activeNodes": ["n315-ctrl-ffi", "n315-bridge-py"], "activeEdges": ["p315-i5"]},
                {"from": "bpy", "to": "rt", "message": "worker_init_request(_WorkerRequest(protos=protos_adapter))", "payload": "V2 indexes function_app.py & starts http_v2 if needed", "activeNodes": ["n315-bridge-py", "n315-rt", "n315-lib"], "activeEdges": ["p315-i6", "p315-i7"]},
                {"from": "rt", "to": "host", "message": "protos_adapter.to_dict() -> py_to_worker_init_response -> prost", "isReturn": True, "payload": "Sent via mpsc<Bytes> to Host", "activeNodes": ["n315-rt", "n315-ctrl-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["p315-i6", "p315-i4", "p315-i2"]},
            ],
        },
        # 2. Worker Specialization
        {
            "id": "specialization",
            "title": "2. Worker Specialization Flow (Namespace-Safe Eviction + Reload)",
            "proto": "FunctionEnvironmentReloadRequest → _clear_modules_from_path → ReloadResponse",
            "scope": "Linux / Flex Consumption Only (Placeholder Mode)",
            "summary": (
                "When specializing a warm R2P2 standby process, `bridge.py` runs **`_clear_modules_from_path(_workers_dir)`**: "
                "file-backed worker modules & cached descendants are evicted and stale child attributes are detached "
                "from retained parents, while **PEP 420 namespace parents (`azure`, `azurefunctions`) without `__file__` "
                "are preserved** so customer SDK/extension children stay attached! Plus zero `grpcio`/`protobuf` C-extensions "
                "ever existed in `sys.modules` to collide with customer pins."
            ),
            "bypassedNote": "Hot invocation seam is cleared (`_control_path_cache.clear()`) and re-bound to the newly selected runtime.",
            "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi", "n315-bridge-py", "n315-rt", "n315-lib", "n315-ext"],
            "topologyEdges": [
                {"id": "p315-s1", "source": "n315-proto", "target": "n315-router", "kind": "grpc-wire", "label": "1. FunctionEnvironmentReloadRequest"},
                {"id": "p315-s2", "source": "n315-router", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "2. env_reload_req_to_py(PyDict)"},
                {"id": "p315-s3", "source": "n315-ctrl-ffi", "target": "n315-bridge-py", "kind": "pyo3-control", "label": "3. _clear_modules_from_path (namespace-safe)"},
                {"id": "p315-s4", "source": "n315-bridge-py", "target": "n315-lib", "kind": "syspath-mutation", "label": "4a. promote customer .python_packages", "dashed": True},
                {"id": "p315-s5", "source": "n315-bridge-py", "target": "n315-ext", "kind": "syspath-mutation", "label": "4b. keep azurefunctions.* namespaces", "dashed": True},
                {"id": "p315-s6", "source": "n315-bridge-py", "target": "n315-rt", "kind": "inproc-contract", "label": "5. reload runtime + env_vars + index"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "ctrl", "label": "bridge.rs (prost/PyO3)"},
                {"id": "bpy", "label": "bridge.py Dep Engine"},
                {"id": "rt", "label": "Runtime + Customer Pkgs"},
            ],
            "steps": [
                {"from": "host", "to": "ctrl", "message": "FunctionEnvironmentReloadRequest(app_dir, env_vars)", "payload": "prost decodes reload request into PyDict", "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi"], "activeEdges": ["p315-s1", "p315-s2"]},
                {"from": "ctrl", "to": "bpy", "message": "_clear_modules_from_path(_workers_dir) + invalidate_caches()", "payload": "Evicts file-backed worker deps; preserves namespace parents (`azure`, `azurefunctions`)", "activeNodes": ["n315-ctrl-ffi", "n315-bridge-py", "n315-ext"], "activeEdges": ["p315-s3", "p315-s5"]},
                {"from": "bpy", "to": "bpy", "message": "_prioritize_customer_dependencies(dir) + _select_runtime(dir)", "payload": "Clears _control_path_cache & re-caches _rt_tls for log correlation", "activeNodes": ["n315-bridge-py", "n315-lib"], "activeEdges": ["p315-s4"]},
                {"from": "bpy", "to": "rt", "message": "function_environment_reload_request(protos=protos_adapter)", "payload": "Reloads os.environ, tzset(), OTel, http_v2, and indexes customer app", "activeNodes": ["n315-bridge-py", "n315-rt"], "activeEdges": ["p315-s6"]},
                {"from": "rt", "to": "host", "message": "py_to_env_reload_response -> prost StreamingMessage", "isReturn": True, "payload": "Specialized without any protobuf descriptor-pool conflicts!", "activeNodes": ["n315-rt", "n315-ctrl-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["p315-s6", "p315-s2", "p315-s1"]},
            ],
        },
        # 3. Metadata & Indexing
        {
            "id": "metadata",
            "title": "3. Worker Metadata & Indexing Flow",
            "proto": "FunctionsMetadataRequest → control.rs → protos_adapter → prost",
            "scope": "V2 Returns Indexed Decorator Metadata; V1 Signals Host Indexing",
            "summary": (
                "Rust `bridge::handle` decodes `FunctionsMetadataRequest` and calls `bridge.handle_control('functions_metadata_request', {})`. "
                "Runtime V2 returns its indexed `RawFunctionMetadata` list wrapped in `protos_adapter` objects (`.to_dict()`), "
                "which `control::py_to_function_metadata_response` serializes into native `prost` wire bytes. "
                "Runtime V1 returns `use_default_metadata_indexing=True`."
            ),
            "bypassedNote": "Hot native tuple FFI (`bridge::invoke`) is unused during metadata discovery.",
            "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi", "n315-bridge-py", "n315-rt"],
            "topologyEdges": [
                {"id": "p315-m1", "source": "n315-proto", "target": "n315-router", "kind": "grpc-wire", "label": "1. FunctionsMetadataRequest"},
                {"id": "p315-m2", "source": "n315-router", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "2. bridge::handle()"},
                {"id": "p315-m3", "source": "n315-ctrl-ffi", "target": "n315-bridge-py", "kind": "pyo3-control", "label": "3. handle_control(dict)"},
                {"id": "p315-m4", "source": "n315-bridge-py", "target": "n315-rt", "kind": "inproc-contract", "label": "4. functions_metadata_request()"},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "ctrl", "label": "bridge.rs + control.rs"},
                {"id": "bpy", "label": "bridge.py + adapter"},
                {"id": "rt", "label": "Runtime v2 / v1"},
            ],
            "steps": [
                {"from": "host", "to": "ctrl", "message": "FunctionsMetadataRequest bytes", "payload": "prost-decoded in Rust", "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi"], "activeEdges": ["p315-m1", "p315-m2"]},
                {"from": "ctrl", "to": "bpy", "message": "handle_control('functions_metadata_request', {})", "payload": "Emits Kusto-compatible Received WorkerMetadataRequest system log", "activeNodes": ["n315-ctrl-ffi", "n315-bridge-py"], "activeEdges": ["p315-m3"]},
                {"from": "bpy", "to": "rt", "message": "_run_coro(_rt.functions_metadata_request(req))", "payload": "V2 returns _metadata_result | V1 returns use_default_metadata_indexing=True", "activeNodes": ["n315-bridge-py", "n315-rt"], "activeEdges": ["p315-m4"]},
                {"from": "rt", "to": "host", "message": "to_dict() -> py_to_function_metadata_response -> prost", "isReturn": True, "payload": "StreamingMessage(FunctionMetadataResponse) bytes", "activeNodes": ["n315-rt", "n315-ctrl-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["p315-m4", "p315-m2", "p315-m1"]},
            ],
        },
        # 4. Function Load (V1)
        {
            "id": "function_load",
            "title": "4. Worker Functions Load Flow (V1 `_metadata_ns` Import vs V2 Ack)",
            "proto": "FunctionLoadRequest → _metadata_ns(SimpleNamespace) → FunctionLoadResponse",
            "scope": "V1 `function.json` Script Loading (`azure_functions_runtime_v1`); V2 Immediate Ack",
            "summary": (
                "For **V1** apps, `control::function_load_req_to_py` decodes `RpcFunctionMetadata` & `BindingInfo` "
                "into a `PyDict`, and `bridge._metadata_ns()` wraps them in `SimpleNamespace` objects matching "
                "protobuf attribute access so `azure_functions_runtime_v1` imports `__init__.py` without `google.protobuf`! "
                "For **V2** apps, `function_load_request` immediately returns `Success`."
            ),
            "bypassedNote": "Hot FFI stays idle; V2 apps return immediate Success while V1 apps import their `__init__.py` entrypoints here.",
            "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi", "n315-bridge-py", "n315-rt", "n315-lib"],
            "topologyEdges": [
                {"id": "p315-l1", "source": "n315-proto", "target": "n315-router", "kind": "grpc-wire", "label": "1. FunctionLoadRequest"},
                {"id": "p315-l2", "source": "n315-router", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "2. function_load_req_to_py(dict)"},
                {"id": "p315-l3", "source": "n315-ctrl-ffi", "target": "n315-bridge-py", "kind": "pyo3-control", "label": "3. _metadata_ns + _binding_ns"},
                {"id": "p315-l4", "source": "n315-bridge-py", "target": "n315-rt", "kind": "inproc-contract", "label": "4. V1 load_function() / V2 ack"},
                {"id": "p315-l5", "source": "n315-rt", "target": "n315-lib", "kind": "exec-dispatch", "label": "5. V1 imports __init__.py", "dashed": True},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "ctrl", "label": "bridge.rs + control.rs"},
                {"id": "bpy", "label": "bridge.py (_metadata_ns)"},
                {"id": "rt", "label": "Runtime V1 (or V2)"},
                {"id": "app", "label": "V1 __init__.py"},
            ],
            "steps": [
                {"from": "host", "to": "ctrl", "message": "FunctionLoadRequest(function_id, metadata)", "payload": "prost decodes bindings & scriptFile", "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-ctrl-ffi"], "activeEdges": ["p315-l1", "p315-l2"]},
                {"from": "ctrl", "to": "bpy", "message": "handle_control('function_load_request', req_dict)", "payload": "_metadata_ns() constructs protobuf-free SimpleNamespace tree", "activeNodes": ["n315-ctrl-ffi", "n315-bridge-py"], "activeEdges": ["p315-l3"]},
                {"from": "bpy", "to": "rt", "message": "await _rt.function_load_request(_WorkerRequest)", "payload": "V2 returns immediate Success; V1 runs load_function()", "activeNodes": ["n315-bridge-py", "n315-rt"], "activeEdges": ["p315-l4"]},
                {"from": "rt", "to": "app", "message": "[V1 Only] Import script_file & register FunctionInfo", "payload": "Populates _functions[function_id]", "activeNodes": ["n315-rt", "n315-lib"], "activeEdges": ["p315-l5"]},
                {"from": "rt", "to": "host", "message": "py_to_function_load_response -> prost bytes", "isReturn": True, "payload": "FunctionLoadResponse(Success)", "activeNodes": ["n315-rt", "n315-ctrl-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["p315-l4", "p315-l2", "p315-l1"]},
            ],
        },
        # 5. Invocation
        {
            "id": "invocation",
            "title": "5. Worker Invocation Flow (Dual Path: Native Datum Tuples vs Extensions)",
            "proto": "InvocationRequest → [Hot: bridge::invoke | Ext: bridge::handle] → InvocationResponse",
            "scope": "Every Trigger Execution (+122% Throughput on Hot Path)",
            "summary": (
                "`main.rs` spawns a concurrent task per request and checks memoized `needs_control_path(function_id)`: "
                "**(A) Hot Path** (standard V2/V1 `python-library` bindings) converts `prost` `TypedData` directly "
                "into PyO3 `(tag, val)` datum tuples (`convert.rs`) and calls `native_invocation.py`—zero Python "
                "protobuf! **(B) Control Path** (`python-extensions` `http_v2` FastAPI streaming or `SdkType` "
                "deferred bindings) routes via `control.rs` `PyDict` + `protos_adapter.py` to `handle_event.py`."
            ),
            "bypassedNote": "Standard functions completely bypass `control.rs`, `protos_adapter.py`, and `handle_event.py`!",
            "activeNodes": ["n315-proto", "n315-tonic", "n315-router", "n315-hot-ffi", "n315-ctrl-ffi", "n315-bridge-py", "n315-native-py", "n315-rt", "n315-lib", "n315-ext"],
            "topologyEdges": [
                {"id": "p315-v1", "source": "n315-proto", "target": "n315-tonic", "kind": "grpc-wire", "label": "1. InvocationRequest (BytesCodec)"},
                {"id": "p315-v2", "source": "n315-tonic", "target": "n315-router", "kind": "thread-queue", "label": "2. tokio::spawn + control_path_cache"},
                {"id": "p315-v3", "source": "n315-router", "target": "n315-hot-ffi", "kind": "pyo3-hot", "label": "3a. Hot: bridge::invoke()"},
                {"id": "p315-v4", "source": "n315-hot-ffi", "target": "n315-native-py", "kind": "pyo3-hot", "label": "4a. invoke_native(datum tuples)"},
                {"id": "p315-v5", "source": "n315-native-py", "target": "n315-lib", "kind": "exec-dispatch", "label": "5a. Datum decode + sync/async fn"},
                {"id": "p315-v6", "source": "n315-router", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "3b. Ext: HTTP-v2 / SdkType", "dashed": True},
                {"id": "p315-v7", "source": "n315-ctrl-ffi", "target": "n315-bridge-py", "kind": "pyo3-control", "label": "4b. handle_invocation_control", "dashed": True},
                {"id": "p315-v8", "source": "n315-bridge-py", "target": "n315-rt", "kind": "inproc-contract", "label": "5b. handle_event + http_v2", "dashed": True},
                {"id": "p315-v9", "source": "n315-rt", "target": "n315-ext", "kind": "pyo3-control", "label": "6b. stream WebApp / SdkType", "dashed": True},
            ],
            "actors": [
                {"id": "host", "label": "Functions Host"},
                {"id": "rust", "label": "Tokio + Router"},
                {"id": "hot", "label": "Hot FFI (convert.rs)"},
                {"id": "native", "label": "native_invocation.py"},
                {"id": "app", "label": "SDK / Extensions / App"},
            ],
            "steps": [
                {"from": "host", "to": "rust", "message": "StreamingMessage(InvocationRequest) -> tokio::spawn", "payload": "Concurrent dispatch; checks control_path_cache(fn_id)", "activeNodes": ["n315-proto", "n315-tonic", "n315-router"], "activeEdges": ["p315-v1", "p315-v2"]},
                {"from": "rust", "to": "hot", "message": "[Hot Path] spawn_blocking -> bridge::invoke(&req)", "payload": "typed_data_to_tuple() converts inputs in Rust", "activeNodes": ["n315-router", "n315-hot-ffi"], "activeEdges": ["p315-v3"]},
                {"from": "hot", "to": "native", "message": "Python::attach -> invoke_native(fn_id, inputs, meta)", "payload": "_InvocShim + OTel context; zero Python protobuf", "activeNodes": ["n315-hot-ffi", "n315-native-py"], "activeEdges": ["p315-v4"]},
                {"from": "native", "to": "app", "message": "Decode python-library Datum + run sync/async handler", "payload": "(Or via handle_invocation_control -> http_v2 / SdkType if Extension)", "activeNodes": ["n315-native-py", "n315-lib", "n315-rt", "n315-ext"], "activeEdges": ["p315-v5", "p315-v8", "p315-v9"]},
                {"from": "app", "to": "host", "message": "tuple_to_typed_data -> prost encode -> mpsc<Bytes>", "isReturn": True, "payload": "754 req/s vs 339 req/s (+122% on GIL build)", "activeNodes": ["n315-lib", "n315-native-py", "n315-hot-ffi", "n315-tonic", "n315-proto"], "activeEdges": ["p315-v5", "p315-v4", "p315-v3", "p315-v1"]},
            ],
        },
        # 6. Worker Status
        {
            "id": "worker_status",
            "title": "6. Worker Status Flow (Zero-GIL Native Rust Fast-Path)",
            "proto": "WorkerStatusRequest → Rust prost → WorkerStatusResponse (0 Python / 0 GIL)",
            "scope": "Host Scale Controller Health Check (Entire CPython Interpreter Bypassed!)",
            "summary": (
                "Major architectural win in R2P2: when `bridge::handle` (`src/bridge.rs:L114`) matches "
                "`Content::WorkerStatusRequest`, it builds `WorkerStatusResponse` in **pure Rust** and pushes "
                "the bytes onto `mpsc<Bytes>` **without calling `Python::attach` and without acquiring the GIL**! "
                "Even if customer Python threads are 100% CPU-saturated holding the GIL, scale probes answer in microseconds."
            ),
            "bypassedNote": "PyO3 GIL boundary, Bridge, Runtime Engine, SDK, Extensions, and User Code are 100% untouched!",
            "activeNodes": ["n315-proto", "n315-tonic", "n315-router"],
            "topologyEdges": [
                {"id": "p315-st1", "source": "n315-proto", "target": "n315-tonic", "kind": "grpc-wire", "label": "1. WorkerStatusRequest bytes"},
                {"id": "p315-st2", "source": "n315-tonic", "target": "n315-router", "kind": "thread-queue", "label": "2. prost match WorkerStatusRequest"},
                {"id": "p315-st3", "source": "n315-router", "target": "n315-tonic", "kind": "thread-queue", "label": "3. WorkerStatusResponse (ZERO GIL!)"},
                {"id": "p315-st4", "source": "n315-tonic", "target": "n315-proto", "kind": "grpc-wire", "label": "4. EventStream reply"},
            ],
            "actors": [
                {"id": "host", "label": "Host Scale Controller"},
                {"id": "tonic", "label": "Tokio + Tonic"},
                {"id": "router", "label": "Rust Router (0 GIL)"},
            ],
            "steps": [
                {"from": "host", "to": "tonic", "message": "StreamingMessage(WorkerStatusRequest)", "payload": "Host health & scale latency probe", "activeNodes": ["n315-proto", "n315-tonic"], "activeEdges": ["p315-st1"]},
                {"from": "tonic", "to": "router", "message": "Match Some(Content::WorkerStatusRequest(_)) in Rust", "payload": "Does NOT call Python::attach — immune to Python GIL contention!", "activeNodes": ["n315-tonic", "n315-router"], "activeEdges": ["p315-st2"]},
                {"from": "router", "to": "host", "message": "prost encode WorkerStatusResponse -> mpsc tx", "isReturn": True, "payload": "Sub-millisecond native reply", "activeNodes": ["n315-router", "n315-tonic", "n315-proto"], "activeEdges": ["p315-st3", "p315-st4"]},
            ],
        },
        # 7. Worker Logs
        {
            "id": "worker_logs",
            "title": "7. Worker Logs Flow (Non-Blocking PyO3 LogSink → Lock-Free Rust mpsc)",
            "proto": "logging.LogRecord → _RpcLogHandler → #[pyclass] LogSink → prost → Host",
            "scope": "Reverse Telemetry Stream (Customer & System Logs → Host)",
            "summary": (
                "Startup logs emit `LanguageWorkerConsoleLog` via `src/log.rs`. Once `bridge.configure()` runs, "
                "`_RpcLogHandler` captures all Python root logs, resolves `invocation_id` from **1) `_rt.invocation_id_cv`** "
                "(async & threadpool handlers) or **2) `_rt_tls` (`context.thread_local_storage.invocation_id`)** "
                "(user-spawned `threading.Thread`s!), and calls `LogSink.emit_log(dict)`. Rust `prost`-encodes `RpcLog` "
                "and pushes onto the lock-free `UnboundedSender<Bytes>` without awaiting or deadlocking the GIL."
            ),
            "bypassedNote": "Flows RIGHT → LEFT from User Code / Runtime into PyO3 `LogSink` and straight onto the outbound tonic stream.",
            "activeNodes": ["n315-lib", "n315-native-py", "n315-bridge-py", "n315-ctrl-ffi", "n315-tonic", "n315-proto"],
            "topologyEdges": [
                {"id": "p315-lg1", "source": "n315-lib", "target": "n315-native-py", "kind": "exec-dispatch", "label": "1. user logging.info() (cv / _rt_tls)"},
                {"id": "p315-lg2", "source": "n315-native-py", "target": "n315-bridge-py", "kind": "inproc-contract", "label": "2. _RpcLogHandler + _current_invocation_id()"},
                {"id": "p315-lg3", "source": "n315-bridge-py", "target": "n315-ctrl-ffi", "kind": "pyo3-control", "label": "3. LogSink.emit_log(flat dict)"},
                {"id": "p315-lg4", "source": "n315-ctrl-ffi", "target": "n315-tonic", "kind": "thread-queue", "label": "4. prost encode -> UnboundedSender<Bytes>"},
                {"id": "p315-lg5", "source": "n315-tonic", "target": "n315-proto", "kind": "grpc-wire", "label": "5. StreamingMessage(RpcLog) → Host"},
            ],
            "actors": [
                {"id": "app", "label": "User Code / User Thread"},
                {"id": "bpy", "label": "bridge.py (_RpcLogHandler)"},
                {"id": "sink", "label": "Rust #[pyclass] LogSink"},
                {"id": "tonic", "label": "mpsc<Bytes> + Tonic"},
                {"id": "host", "label": "Host (AppInsights / Kusto)"},
            ],
            "steps": [
                {"from": "app", "to": "bpy", "message": "logging.info(...) from handler or custom threading.Thread", "payload": "Intercepted by root _RpcLogHandler", "activeNodes": ["n315-lib", "n315-native-py", "n315-bridge-py"], "activeEdges": ["p315-lg1", "p315-lg2"]},
                {"from": "bpy", "to": "bpy", "message": "Resolve _current_invocation_id() + System vs User category", "payload": "1) _rt.invocation_id_cv -> 2) _rt_tls (context.thread_local_storage)", "activeNodes": ["n315-bridge-py"], "activeEdges": []},
                {"from": "bpy", "to": "sink", "message": "sink.emit_log({level, message, category, invocation_id})", "payload": "Passes primitive Python dict — zero Python protobuf!", "activeNodes": ["n315-bridge-py", "n315-ctrl-ffi"], "activeEdges": ["p315-lg3"]},
                {"from": "sink", "to": "tonic", "message": "py_log_to_streaming_message -> tx.send(Bytes)", "payload": "Non-blocking lock-free mpsc send; never deadlocks while holding GIL", "activeNodes": ["n315-ctrl-ffi", "n315-tonic"], "activeEdges": ["p315-lg4"]},
                {"from": "tonic", "to": "host", "message": "Drain UnboundedReceiverStream onto EventStream", "isReturn": True, "payload": "Delivered to Host AppInsights / Kusto", "activeNodes": ["n315-tonic", "n315-proto"], "activeEdges": ["p315-lg5"]},
            ],
        },
    ]
