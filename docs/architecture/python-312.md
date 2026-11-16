# Python ≤ 3.12 Architecture — Monolithic Worker

For **Python 3.7 through 3.12**, the worker ships as a single monolithic Python package under [`workers/azure_functions_worker`](https://github.com/Azure/azure-functions-python-worker/tree/dev/workers/azure_functions_worker), launched by [`workers/python/prodV4/worker.py`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/python/prodV4/worker.py).

Transport (`grpcio` + `google.protobuf`), `DependencyManager`, function indexing (`loader.py`), binding serialization (`bindings/`), shared-memory transfer (`SharedMemoryManager`), HTTP v2 streaming (`http_v2.py`), worker extensions (`extension.py`), and the synchronous `ThreadPoolExecutor` (`_sync_call_tp`) all reside inside one coupled module tree.

<div class="arch-atlas-mount" data-era="py312" data-phase="init"></div>

---

## Architecture & Component Reference

<!-- BEGIN AUTO-GENERATED: py312-components -->

### Full Static Topology (Mermaid)

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"ServerDuplexChannel"| n312_proto
  n312_proto -->|"EventStream (grpcio)"| n312_grpc
  n312_boot -->|"boot + DependencyManager"| n312_disp
  n312_grpc -->|"call_soon_threadsafe / Queue"| n312_disp
  n312_disp -->|"index & load"| n312_load
  n312_disp -->|"TypedData <-> args"| n312_bind
  n312_load -->|"inspect @app / function.json"| n312_sdk
  n312_bind -->|"Datum decode + invoke"| n312_sdk
  n312_bind -.->|"WebApp / SdkType"| n312_ext
```

### Component & Source Reference

| Component | Repository | Source Anchor | Responsibility |
| --- | --- | --- | --- |
| **Script Host (WorkerChannel)** | `functions-host` | [`src/WebJobs.Script.Grpc/Channel/WorkerChannel.cs`](https://github.com/Azure/azure-functions-host/blob/dev/src/WebJobs.Script.Grpc/Channel/WorkerChannel.cs) | .NET Functions Host runtime spawning `prodV4/worker.py`, driving triggers, scale probes, and telemetry. |
| **FunctionRpc.proto Contract** | `worker-protobuf` | [`src/proto/FunctionRpc.proto`](https://github.com/Azure/azure-functions-language-worker-protobuf/blob/dev/src/proto/FunctionRpc.proto) | Language-neutral gRPC `.proto` contract between `azure-functions-host` and `azure_functions_worker`. |
| **prodV4/worker.py & main.py** | `python-worker` | [`workers/azure_functions_worker/main.py:L70`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/azure_functions_worker/main.py#L70) | Sets worker-first sys.path so bundled `grpcio`/`protobuf` import cleanly, then starts asyncio loop. |
| **gRPC Pump (__poll_grpc)** | `python-worker` | [`workers/azure_functions_worker/dispatcher.py:L155`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/azure_functions_worker/dispatcher.py#L155) | Background OS thread reading `stub.EventStream` and posting tasks via `call_soon_threadsafe`. |
| **Monolithic Dispatcher** | `python-worker` | [`workers/azure_functions_worker/dispatcher.py:L90`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/azure_functions_worker/dispatcher.py#L90) | Central class owning message routing, logging switch, OTel/AppInsights setup, and `_sync_call_tp`. |
| **DependencyManager** | `python-worker` | [`workers/azure_functions_worker/utils/dependency.py:L25`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/azure_functions_worker/utils/dependency.py#L25) | Manages worker-first placeholder boot vs customer `.python_packages` promotion on Init/Specialization. |
| **Loader & ExtensionManager** | `python-worker` | [`workers/azure_functions_worker/loader.py:L249`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/azure_functions_worker/loader.py#L249) | Indexes V2 `@app` decorators or V1 `function.json` files and invokes `AppExtensionBase` hooks. |
| **Bindings, SharedMem & http_v2** | `python-worker` | [`workers/azure_functions_worker/http_v2.py:L261`](https://github.com/Azure/azure-functions-python-worker/blob/dev/workers/azure_functions_worker/http_v2.py#L261) | Converts `protos.TypedData` <-> `Datum`, manages shared-memory rings, and coordinates HTTP v2 streaming. |
| **azure-functions SDK** | `python-library` | [`azure/functions/meta.py`](https://github.com/Azure/azure-functions-python-library/blob/dev/azure/functions/meta.py) | Customer decorators, trigger/binding models (`HttpRequest`, `QueueMessage`), and `Datum` converters. |
| **azurefunctions-extensions-*** | `python-extensions` | [`azurefunctions-extensions-base/azurefunctions/extensions/base/sdkType.py`](https://github.com/Azure/azure-functions-python-extensions/blob/dev/azurefunctions-extensions-base/azurefunctions/extensions/base/sdkType.py) | Optional HTTP v2 ASGI streaming (`WebApp`) and deferred SDK bindings (`BlobClient`, etc.). |

<!-- END AUTO-GENERATED: py312-components -->

---

## The 7 Worker Lifecycle Phases (Python ≤ 3.12)

Each Host ↔ Worker lifecycle phase exercises a distinct subset of components and interactions in `azure_functions_worker`.

<!-- BEGIN AUTO-GENERATED: py312-phases -->

### 1. Worker Initialization Flow


---

- **Wire Protocol:** `StartStream → WorkerInitRequest → WorkerInitResponse`

---

- **Execution Scope:** All SKUs (Cold Start)


---

Host spawns `prodV4/worker.py`, which boots `azure_functions_worker` with worker dependencies isolated first (`grpcio` + `protobuf`). Once `EventStream` connects and sends `StartStream`, `WorkerInitRequest` negotiates capabilities (`SHARED_MEMORY`, `RAW_HTTP_BODY_BYTES`, `WORKER_STATUS`), initializes OTel/AppInsights, promotes customer `.python_packages` (on Dedicated/EP), loads the binding registry, and optionally pre-indexes if `PYTHON_ENABLE_INIT_INDEXING=1`.


---

> **Bypassed / Idle Note:** In Linux Consumption placeholder mode, customer packages are NOT mounted yet during Init (deferred to Phase 2 Specialization).


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant host as Functions Host
  participant boot as prodV4 + main.py
  participant grpc as gRPC Thread
  participant disp as Monolith Dispatcher
  participant dep as DependencyManager
  host->>boot: Spawn python prodV4/worker.py --host --port --workerId
  boot->>grpc: Dispatcher.connect() opens insecure grpcio channel
  grpc-->>host: Send StartStream(worker_id) + detach console logger
  host->>disp: WorkerInitRequest(capabilities, function_app_directory)
  disp->>dep: should_load_cx_dependencies() -> prioritize_customer_deps()
  disp->>disp: Configure OTel/AppInsights + bindings.load_binding_registry()
  disp-->>host: WorkerInitResponse(capabilities, worker_metadata)
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"WorkerChannel"| n312_proto
  n312_proto -->|"1. spawn prodV4/worker.py"| n312_boot
  n312_boot -->|"2. use_worker_deps + connect()"| n312_grpc
  n312_grpc -->|"3. StartStream(worker_id)"| n312_proto
  n312_proto -->|"4. WorkerInitRequest"| n312_grpc
  n312_grpc -->|"5. call_soon_threadsafe"| n312_disp
  n312_disp -->|"6. prioritize_customer_deps()"| n312_dep
  n312_disp -->|"7. load_binding_registry()"| n312_bind
```

---

### 2. Worker Specialization Flow (Consumption Placeholder)


---

- **Wire Protocol:** `FunctionEnvironmentReloadRequest → FunctionEnvironmentReloadResponse`

---

- **Execution Scope:** Linux / Flex Consumption Only (Placeholder Mode)


---

Warm standby containers boot before any customer app is assigned. When specialized, the Host mounts the customer package and sends `FunctionEnvironmentReloadRequest` carrying `function_app_directory` and `environment_variables`. The monolith clears `os.environ`, calls `time.tzset()`, clears `sys.path_importer_cache`, promotes customer `.python_packages`, recreates `_sync_call_tp` (`PYTHON_THREADPOOL_THREAD_COUNT`), and changes `cwd`.


---

> **Bypassed / Idle Note:** Never sent on Dedicated/Premium cold boots or worker restarts (those go straight through WorkerInit).


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant host as Functions Host
  participant disp as Monolith Dispatcher
  participant dep as DependencyManager
  participant sdk as Customer Packages
  host->>disp: FunctionEnvironmentReloadRequest(app_dir, env_vars)
  disp->>disp: os.environ.clear() + apply env_vars + time.tzset()
  disp->>dep: sys.path_importer_cache.clear() + prioritize_customer_deps()
  disp->>disp: bindings.load_binding_registry() + os.chdir(app_dir)
  disp-->>host: FunctionEnvironmentReloadResponse(capabilities)
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"WorkerChannel"| n312_proto
  n312_proto -->|"1. FunctionEnvironmentReloadRequest"| n312_grpc
  n312_grpc -->|"2. _dispatch_grpc_request"| n312_disp
  n312_disp -->|"3. reload os.environ + sys.path"| n312_dep
  n312_dep -.->|"4. reload customer azure.functions"| n312_sdk
  n312_disp -->|"5. optional init indexing + http_v2"| n312_load
  n312_disp -->|"6. recreate _sync_call_tp + bindings"| n312_bind
```

---

### 3. Worker Metadata & Indexing Flow


---

- **Wire Protocol:** `FunctionsMetadataRequest → FunctionMetadataResponse`

---

- **Execution Scope:** V2 Worker-Indexed Apps (Returns Fallback Flag for V1)


---

Host asks the worker whether it owns function discovery. In `≤ 3.12`, `load_function_metadata()` checks if `function_app.py` exists: for **V2**, it imports `function_app.py`, walks `@app` decorators and `Blueprint`s (`python-library`) plus `WebApp`/`SdkType` hooks (`python-extensions`), and returns `RawFunctionMetadata` (`use_default_metadata_indexing=False`). For **V1**, it returns `use_default_metadata_indexing=True` so the Host scans `function.json` directories itself.


---

> **Bypassed / Idle Note:** For V1 apps (`function.json`), no customer Python code is imported during Metadata — Host falls back to disk scanning.


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant host as Functions Host
  participant disp as Monolith Dispatcher
  participant load as loader.py
  participant sdk as python-library / App
  host->>disp: FunctionsMetadataRequest(function_app_directory)
  disp->>load: Check os.path.exists(function_app.py)
  load->>sdk: [V2] index_function_app() -> import function_app.py
  load-->>disp: Register FunctionInfo in _functions + build RawFunctionMetadata
  disp-->>host: FunctionMetadataResponse(results, use_default_metadata_indexing)
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"WorkerChannel"| n312_proto
  n312_proto -->|"1. FunctionsMetadataRequest"| n312_grpc
  n312_grpc -->|"2. _handle__functions_metadata_request"| n312_disp
  n312_disp -->|"3. load_function_metadata()"| n312_load
  n312_load -->|"4a. V2: import function_app & @app"| n312_sdk
  n312_load -.->|"4b. inspect WebApp / SdkType"| n312_ext
```

---

### 4. Worker Functions Load Flow (V1 Primary)


---

- **Wire Protocol:** `FunctionLoadRequest → FunctionLoadResponse`

---

- **Execution Scope:** V1 Programming Model (`function.json`); V2 Multi-Worker / Ack


---

After the Host parses `function.json` files for a **V1** app, it sends one `FunctionLoadRequest` per function with `script_file`, `entry_point`, and `bindings`. `loader.load_function()` imports the target Python module (`__init__.py`), validates parameter type annotations against `bindings/`, and stores `FunctionInfo` in `self._functions`. (For V2 single-worker, `_functions` already holds the function from Phase 3, so it fast-acks; for 2nd+ workers in multi-proc mode, it triggers lazy V2 indexing).


---

> **Bypassed / Idle Note:** For standard V2 apps, user scripts were already loaded in Phase 3 Metadata, making FunctionLoad a fast registry check.


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant host as Functions Host
  participant disp as Monolith Dispatcher
  participant load as loader.py
  participant app as V1 __init__.py
  host->>disp: FunctionLoadRequest(function_id, RpcFunctionMetadata)
  disp->>load: loader.load_function(name, dir, script_file, entry_point)
  load->>app: importlib.import_module() -> resolve main() callable
  disp->>disp: _functions.add_function(function_id, func, metadata)
  disp-->>host: FunctionLoadResponse(function_id, Success)
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"WorkerChannel"| n312_proto
  n312_proto -->|"1. FunctionLoadRequest(metadata)"| n312_grpc
  n312_grpc -->|"2. _handle__function_load_request"| n312_disp
  n312_disp -->|"3. loader.load_function(script_file)"| n312_load
  n312_load -->|"4. importlib import __init__.py"| n312_sdk
  n312_disp -->|"5. validate binding types & add_function"| n312_bind
```

---

### 5. Worker Invocation Flow


---

- **Wire Protocol:** `InvocationRequest → InvocationResponse`

---

- **Execution Scope:** Every Function Trigger Execution


---

Host sends `InvocationRequest` with `input_data` (`TypedData` or POSIX/Win shared-memory map) and `trigger_metadata`. `Dispatcher` decodes bindings via `python-library` (`Datum`) or `python-extensions` (`SdkType` / `http_v2`), sets W3C OpenTelemetry context, executes `async def` on the event loop or `def` on `_sync_call_tp`, and marshals `Out[T]` + `$return` back to protobuf.


---

> **Bypassed / Idle Note:** `prodV4` boot and `loader.py` are idle during steady-state invocations.


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant host as Functions Host
  participant disp as Monolith Dispatcher
  participant bind as Bindings / SharedMem
  participant app as SDK & User Handler
  host->>disp: InvocationRequest(invocation_id, function_id, input_data)
  disp->>bind: from_incoming_proto() + get_context() + OTel traceparent
  bind->>app: Execute async coroutine or run_in_executor(_sync_call_tp)
  app-->>disp: to_outgoing_proto($return, Out) + sys.stdout.flush()
  disp-->>host: Enqueue StreamingMessage(invocation_response)
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"WorkerChannel"| n312_proto
  n312_proto -->|"1. InvocationRequest"| n312_grpc
  n312_grpc -->|"2. call_soon_threadsafe"| n312_disp
  n312_disp -->|"3. from_incoming_proto / ShMem"| n312_bind
  n312_bind -.->|"4a. http_v2 / SdkType"| n312_ext
  n312_bind -->|"4b. await / _sync_call_tp"| n312_sdk
  n312_disp -->|"5. _grpc_resp_queue.put"| n312_grpc
```

---

### 6. Worker Status Flow (Host Health & Scale Probe)


---

- **Wire Protocol:** `WorkerStatusRequest → WorkerStatusResponse`

---

- **Execution Scope:** Host Scale Controller & Worker Health Monitoring


---

The Host periodically sends `WorkerStatusRequest` to measure worker round-trip responsiveness for out-of-proc scaling decisions. In `≤ 3.12`, `_handle__worker_status_request` suppresses all logging and returns an empty `WorkerStatusResponse` immediately—**however**, it still hop-schedules onto the single Python `asyncio` event loop and acquires the GIL.


---

> **Bypassed / Idle Note:** Loader, Bindings, SDK, Extensions, and User Code are completely untouched — pure transport/loop health probe.


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant host as Host Scale Controller
  participant grpc as gRPC Thread
  participant disp as Dispatcher (asyncio)
  host->>grpc: WorkerStatusRequest(request_id)
  grpc->>disp: call_soon_threadsafe(_handle__worker_status_request)
  disp-->>host: WorkerStatusResponse() via _grpc_resp_queue
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_host -->|"WorkerChannel"| n312_proto
  n312_proto -->|"1. WorkerStatusRequest"| n312_grpc
  n312_grpc -->|"2. call_soon_threadsafe (GIL + loop)"| n312_disp
  n312_disp -->|"3. WorkerStatusResponse (no logs)"| n312_grpc
  n312_grpc -->|"4. EventStream reply"| n312_proto
```

---

### 7. Worker Logs Flow (Worker → Host Reverse Stream)


---

- **Wire Protocol:** `Python logging.LogRecord → StreamingMessage(RpcLog) → Host`

---

- **Execution Scope:** Reverse Telemetry Stream (System & Customer Logs)


---

Before `EventStream` connects, logs print to stdout/stderr with prefix `LanguageWorkerConsoleLog`. Once connected, `disable_console_logging()` detaches console output and attaches `AsyncLoggingHandler` to the root logger. Every `logging.info/error` from customer code (`User` category) or worker (`System` category) is stamped with `invocation_id` (from task/thread-local) and pushed **back to the Host** on `_grpc_resp_queue` as `RpcLog` messages for Application Insights & Kusto.


---

> **Bypassed / Idle Note:** Originates inside User Code or Worker internals and flows RIGHT → LEFT back to the Host without a Host request.


---

#### Sequence Diagram


---

```mermaid
sequenceDiagram
  participant app as User Code / Worker
  participant disp as AsyncLoggingHandler
  participant grpc as _grpc_resp_queue
  participant host as Host (AppInsights / Kusto)
  app->>disp: logging.info('Order processed') / logger.info(...)
  disp->>disp: Classify System vs User + resolve invocation_id
  disp->>grpc: put_nowait(StreamingMessage(rpc_log=RpcLog(...)))
  grpc-->>host: Stream RpcLog frame over EventStream to Host
```


---

#### Phase Compound Topology


---

```mermaid
flowchart LR
  subgraph c312_host["Functions Host (.NET — azure-functions-host)"]
    n312_host["Script Host (WorkerChannel)<br/>(functions-host)"]
  end
  subgraph c312_wire["Wire Contract (worker-protobuf)"]
    n312_proto["FunctionRpc.proto Contract<br/>(worker-protobuf)"]
  end
  subgraph c312_worker["Monolithic Worker Process (workers/azure_functions_worker)"]
    subgraph c312_trans["gRPC Transport & Isolation"]
      n312_boot["prodV4/worker.py & main.py<br/>(python-worker)"]
      n312_grpc["gRPC Pump (__poll_grpc)<br/>(python-worker)"]
      n312_disp["Monolithic Dispatcher<br/>(python-worker)"]
      n312_dep["DependencyManager<br/>(python-worker)"]
    end
    subgraph c312_eng["In-Tree Indexing, Bindings & Executor"]
      n312_load["Loader & ExtensionManager<br/>(python-worker)"]
      n312_bind["Bindings, SharedMem & http_v2<br/>(python-worker)"]
    end
  end
  subgraph c312_eco["SDK, Extensions & Customer App"]
    n312_sdk["azure-functions SDK<br/>(python-library)"]
    n312_ext["azurefunctions-extensions-*<br/>(python-extensions)"]
  end
  n312_proto -->|"AppInsights / Kusto"| n312_host
  n312_sdk -->|"1. logging.info() -> AsyncLoggingHandler"| n312_disp
  n312_disp -->|"2. stamp invocation_id -> _grpc_resp_queue"| n312_grpc
  n312_grpc -->|"3. StreamingMessage(rpc_log) → Host"| n312_proto
```

<!-- END AUTO-GENERATED: py312-phases -->
