# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FFI bridge between the Rust proxy worker and the Python v2 runtime.

The Rust side owns the gRPC transport (tonic) and embeds CPython (PyO3). It
decodes/encodes every ``StreamingMessage`` with prost and calls into this module
with plain Python values (dicts / datum tuples), getting plain values back. NO
protobuf or gRPC toolchain runs in the Python process; request routing lives on
the Rust side (see src/bridge.rs + src/control.rs).

This mirrors what ``proxy_worker/dispatcher.py`` does, minus the console<->gRPC
logging switch and OpenTelemetry (out of scope here). Dependency handling:

* **Customer dependency priority.** ``configure`` orders ``sys.path`` so the
  customer's installed packages (``.python_packages``) take precedence over the
  worker's bundled deps -- the same search order the proxy worker's
  ``DependencyManager.prioritize_customer_dependencies`` produces (customer deps
  -> worker runtime deps -> app dir). This lets an app pin its own
  ``azure-functions`` (etc.) and actually have it loaded.
* **No protobuf.** The worker links NO ``google.protobuf`` and no gRPC
  toolchain. Rust (prost/tonic) owns every byte on the wire; this bridge speaks
  to the runtime through ``protos_adapter`` -- a pure-Python stand-in for the
  ``protos`` object the runtime expects. That removes the descriptor-pool
  version coupling the classic worker carried (an app may ship any protobuf, or
  none, without affecting the worker). See protos_adapter.py + D-029.

Contract exposed to Rust (Rust owns all prost encoding/decoding):
    configure(workers_dir, function_app_directory, host, request_id, sink)
    handle_control(verb, req: dict) -> dict | None   # control-plane verbs
    handle_invocation_control(req: dict) -> dict | None  # deferred / http-v2
    invoke_native(function_id, invocation_id, inputs, meta) -> tuple  # hot path
    requires_control_path(function_id) -> bool
    log_unhandled(desc) -> None
    shutdown() -> None
"""
import asyncio
import logging
import os
import sys
import threading
import traceback
from types import SimpleNamespace

# Protobuf-free ``protos`` stand-in (see protos_adapter.py + D-029). The runtime
# handlers are transport-agnostic: they read request fields off
# ``request.request.<verb>`` and build responses through a ``protos`` object
# injected at worker_init. The classic worker injects the ``google.protobuf``
# gencode; the Rust worker injects THIS pure-Python module, so nothing in the
# worker process links ``google.protobuf`` or the gRPC toolchain. Rust (prost)
# owns all wire encoding; the adapter objects only carry the shapes + a
# ``to_dict()`` Rust maps back onto the wire. Imported at module load (before
# configure() prepends the customer app dir) so it always resolves to the
# package next to this module and never to a same-named module the app ships.
import protos_adapter as protos  # noqa: E402

# RpcLog level + category enum values (resolved once from the bridge's protos).
_RpcLog = protos.RpcLog
_LOG_LEVEL_CRITICAL = _RpcLog.Critical
_LOG_LEVEL_ERROR = _RpcLog.Error
_LOG_LEVEL_WARNING = _RpcLog.Warning
_LOG_LEVEL_INFO = _RpcLog.Information
_LOG_LEVEL_DEBUG = _RpcLog.Debug
_LOG_CATEGORY_SYSTEM = _RpcLog.RpcLogCategory.Value("System")
_LOG_CATEGORY_USER = _RpcLog.RpcLogCategory.Value("User")


def _level_to_rpc(levelno):
    if levelno >= logging.CRITICAL:
        return _LOG_LEVEL_CRITICAL
    if levelno >= logging.ERROR:
        return _LOG_LEVEL_ERROR
    if levelno >= logging.WARNING:
        return _LOG_LEVEL_WARNING
    if levelno >= logging.INFO:
        return _LOG_LEVEL_INFO
    return _LOG_LEVEL_DEBUG


_rt = None
# The runtime's ``bindings.context._invocation_id_local`` (a threading.local),
# cached in configure(). This is the SAME object returned by
# ``Context.thread_local_storage``; customer code stamps the invocation id onto
# it inside user-spawned threads (``context.thread_local_storage.invocation_id =
# context.invocation_id``). Reading it back in _current_invocation_id restores
# user-thread log correlation (parity with the classic azure_functions_worker,
# where get_context and the log handler shared one threading.local). None until
# configure() selects a runtime.
_rt_tls = None
# Fully-qualified package name of the selected runtime, set in configure().
# "azure_functions_runtime" (v2, default) or "azure_functions_runtime_v1" (v1).
# Used to import runtime-specific submodules (native_invocation, datumdef,
# handle_event) from whichever programming model the app targets.
_rt_name = "azure_functions_runtime"
_host = ""
_function_app_directory = ""

# Rust-owned LogSink + worker request id, set in configure(). The bridge routes
# both worker/system logs and user function logs to the Host as RpcLog
# StreamingMessages through this sink. See docs/rustworker/logging-design.md.
_log_sink = None
_request_id = ""
_rpc_logging_installed = False

# Persistent asyncio loop running on a dedicated thread. The runtime handlers are
# coroutines; we drive them exactly like the real dispatcher's event loop.
_loop = None
_loop_thread = None


_CONSOLE_LOG_PREFIX = "LanguageWorkerConsoleLog"

# System-log namespaces (App Insights vs Kusto routing): a logger whose name
# starts with one of these is a System log; everything else (customer code logs
# under `root`/their own names) is a User log. Mirrors
# proxy_worker/logging.py:is_system_log_category.
_SYSTEM_LOG_PREFIX = "azure_functions_runtime"
_SDK_LOG_PREFIX = "azure.functions"

# Logger used for the worker's own per-message/system logs (System category).
_syslog = logging.getLogger(_SYSTEM_LOG_PREFIX)


def _log(msg, level="INFO"):
    # Match the Python proxy worker's console format
    # (`LanguageWorkerConsoleLog <LEVEL>: <message>`) and stream split
    # (errors -> stderr, everything else -> stdout). See
    # proxy_worker/logging.py.
    stream = sys.stderr if level == "ERROR" else sys.stdout
    print(f"{_CONSOLE_LOG_PREFIX} {level}: {msg}", file=stream, flush=True)


def _is_system_log_category(name):
    return (name.startswith(_SYSTEM_LOG_PREFIX)
            or name.startswith(_SDK_LOG_PREFIX))


def _current_invocation_id():
    """Current invocation id for log correlation.

    Resolution order:

    1. The runtime ``invocation_id_cv`` contextvar -- set by run_sync_func
       (sync handler thread) and by invocation_request_native around the async
       await (see native_invocation.py). Covers logs emitted on the thread that
       runs the handler.
    2. The runtime's ``bindings.context._invocation_id_local`` threading.local
       (== ``context.thread_local_storage``) -- customer code sets this inside
       user-spawned threads. Contextvars are NOT copied into a manually started
       ``threading.Thread``, so without this a log emitted from a user thread
       (e.g. a ThreadPoolExecutor task) would carry no invocation_id and the
       Host would drop it. Mirrors the classic azure_functions_worker, where
       get_context and get_current_invocation_id shared one threading.local.

    Returns None outside an invocation. Both runtimes (v2 and v1) export
    ``invocation_id_cv`` and ``bindings.context._invocation_id_local``.
    """
    try:
        if _rt is not None:
            val = _rt.invocation_id_cv.get()
            if val is not None:
                return val
    except Exception:
        pass
    try:
        if _rt_tls is not None:
            val = getattr(_rt_tls, "invocation_id", None)
            if val is not None:
                return val
    except Exception:
        pass
    return None


def _worker_version():
    try:
        return _rt.version.VERSION
    except Exception:
        return "unknown"


class _RpcLogHandler(logging.Handler):
    """Root-logger handler: LogRecord -> RpcLog StreamingMessage -> Rust sink.

    Direct port of proxy_worker dispatcher.on_logging, but the transport is the
    Rust LogSink (one outbound gRPC stream) instead of an in-process gRPC queue.
    User records carry the current invocation_id so the Host can correlate them
    in Application Insights.
    """

    def emit(self, record):
        sink = _log_sink
        if sink is None:
            return
        try:
            msg = self.format(record)
            level = _level_to_rpc(record.levelno)
            if _is_system_log_category(record.name):
                log_category = _LOG_CATEGORY_SYSTEM
            else:
                log_category = _LOG_CATEGORY_USER
            fields = dict(
                level=level,
                message=msg,
                category=record.name,
                log_category=log_category,
            )
            inv = _current_invocation_id()
            if inv is not None:
                fields["invocation_id"] = inv
            sink.emit_log(fields)
        except Exception as e:  # never recurse into logging
            print(f"{_CONSOLE_LOG_PREFIX} ERROR: rpc-log emit failed: {e}",
                  file=sys.stderr, flush=True)


def _install_rpc_logging():
    """Attach the RpcLog handler to the root logger (idempotent)."""
    global _rpc_logging_installed
    if _rpc_logging_installed or _log_sink is None:
        return
    debug = os.environ.get(
        "PYTHON_ENABLE_DEBUG_LOGGING", "0").strip().lower() in ("1", "true")
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(_RpcLogHandler())
    _rpc_logging_installed = True


def _start_loop():
    global _loop, _loop_thread
    if _loop is not None:
        return
    _loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_loop)
        _loop.run_forever()

    _loop_thread = threading.Thread(
        target=_run, name="bridge-asyncio", daemon=True)
    _loop_thread.start()


def _run_coro(coro):
    """Submit a coroutine to the bridge loop and block for its result.

    ``concurrent.futures.Future.result()`` waits on a threading primitive, which
    releases the GIL, so the loop thread can make progress while Rust's calling
    thread is parked here. No deadlock.
    """
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    return fut.result()


def _reprioritize_path(path, front):
    """Place *path* on ``sys.path`` at a defined priority.

    De-dupes (removes any existing occurrences first) and clears the importer
    cache for the path so a freshly ordered entry is honoured on the next
    import. ``front=True`` gives highest priority; ``front=False`` lowest.
    """
    if not path:
        return
    sys.path[:] = [p for p in sys.path if p != path]
    if front:
        sys.path.insert(0, path)
    else:
        sys.path.append(path)
    sys.path_importer_cache.pop(path, None)


def _customer_deps_path(function_app_directory):
    """Locate the customer's installed-deps dir (``.python_packages``).

    Mirrors the Azure layout the Host provisions
    (``<app>/.python_packages/lib/site-packages``); falls back to any matching
    entry the Host already placed on ``sys.path``. Returns ``""`` if none
    exists (e.g. an app with no third-party deps, or local dev).
    """
    suffix = os.path.join(".python_packages", "lib", "site-packages")
    candidates = []
    if function_app_directory:
        candidates.append(os.path.join(function_app_directory, suffix))
    candidates.extend(p for p in sys.path if p.endswith(suffix))
    for c in candidates:
        if os.path.isdir(c):
            return c
    return ""


def configure(workers_dir, function_app_directory, host, request_id="",
              log_sink=None):
    """Wire up imports and the runtime. Called once from Rust before use."""
    global _rt, _rt_name, _rt_tls, _host, _function_app_directory, \
        _log_sink, _request_id
    _host = host or ""
    _function_app_directory = function_app_directory
    _log_sink = log_sink
    _request_id = request_id or ""

    # Order sys.path so the CUSTOMER's dependencies win over the worker's
    # bundled deps -- mirroring proxy_worker DependencyManager
    # .prioritize_customer_dependencies. Final search order (highest first):
    #   1. customer deps (.python_packages)  -- so an app can pin azure-functions
    #   2. worker runtime deps (workers_dir) -- azure_functions_runtime lives here
    #   3. customer app dir                  -- function_app.py for indexing
    # ``protos_adapter`` was imported at module load, so the runtime's
    # protobuf-free control-plane surface is fixed before this reordering.
    if workers_dir:
        _reprioritize_path(workers_dir, front=True)
    cx_deps = _customer_deps_path(function_app_directory)
    if cx_deps:
        _reprioritize_path(cx_deps, front=True)
    if function_app_directory:
        _reprioritize_path(function_app_directory, front=False)

    # Select the runtime by programming model, mirroring
    # proxy_worker/dispatcher.reload_library_worker: if the app ships the v2
    # script file (``function_app.py`` by default, overridable via
    # PYTHON_SCRIPT_FILE_NAME) it targets the v2 runtime; otherwise it is a
    # classic v1 (function.json) app and uses the v1 runtime. Both runtimes
    # expose the same public API + a ``native_invocation`` fast path, so the
    # rest of the bridge is runtime-agnostic.
    script_file = os.environ.get(
        "PYTHON_SCRIPT_FILE_NAME", "function_app.py")
    v2_scriptfile = os.path.join(function_app_directory or "", script_file)
    if os.path.exists(v2_scriptfile):
        import azure_functions_runtime as rt  # noqa
        _rt_name = "azure_functions_runtime"
    else:
        import azure_functions_runtime_v1 as rt  # noqa
        _rt_name = "azure_functions_runtime_v1"

    _rt = rt

    # Cache the runtime's Context thread-local so _current_invocation_id can
    # correlate logs emitted from user-spawned threads (see its docstring).
    try:
        import importlib
        _rt_tls = importlib.import_module(
            f"{_rt_name}.bindings.context")._invocation_id_local
    except Exception as e:
        _rt_tls = None
        _log(f"WARNING: could not cache runtime thread-local for log "
             f"correlation: {e}")

    _start_loop()
    # Route worker/system + user logs to the Host as RpcLog now that the runtime
    # (and its invocation_id contextvar) is importable and the sink is set.
    _install_rpc_logging()
    _log(f"Bridge configured. runtime={_rt_name!r} host={_host!r} "
         f"app_dir={function_app_directory!r} "
         f"cx_deps={cx_deps!r} "
         f"python={sys.version.split()[0]}")


class _WorkerRequest:
    """Same shape the dispatcher passes to the runtime."""
    __slots__ = ("name", "request", "properties")

    def __init__(self, name, request, properties=None):
        self.name = name
        self.request = request
        self.properties = properties


def _binding_ns(b):
    """One BindingInfo (v1 function.json binding) as an attribute object."""
    return SimpleNamespace(
        type=b.get("type", ""),
        direction=int(b.get("direction", 0)),
        data_type=int(b.get("data_type", 0)),
    )


def _metadata_ns(m):
    """RpcFunctionMetadata (v1 function_load) as an attribute object."""
    if m is None:
        return None
    return SimpleNamespace(
        name=m.get("name", ""),
        directory=m.get("directory", ""),
        script_file=m.get("script_file", ""),
        entry_point=m.get("entry_point", ""),
        bindings={k: _binding_ns(v)
                  for k, v in (m.get("bindings") or {}).items()},
    )


def _build_control_message(verb, req):
    """Turn Rust's decoded request dict into the ``request.request.<verb>``
    attribute shape the (unchanged) runtime handlers read. String maps
    (capabilities/env vars) stay dicts; nested messages become namespaces."""
    if verb == "worker_init_request":
        msg = SimpleNamespace(
            capabilities=dict(req.get("capabilities") or {}),
            function_app_directory=req.get("function_app_directory", ""),
            host_version=req.get("host_version", ""))
    elif verb == "functions_metadata_request":
        msg = SimpleNamespace()
    elif verb == "function_load_request":
        msg = SimpleNamespace(
            function_id=req.get("function_id", ""),
            metadata=_metadata_ns(req.get("metadata")))
    elif verb == "function_environment_reload_request":
        msg = SimpleNamespace(
            function_app_directory=req.get("function_app_directory", ""),
            environment_variables=dict(req.get("environment_variables") or {}))
    else:
        return None
    return SimpleNamespace(**{verb: msg})


def _log_control_received(verb):
    """System log line per inbound control verb (parity with the proxy worker's
    `Received WorkerInitRequest, ...`)."""
    try:
        if verb == "worker_init_request":
            _syslog.info(
                "Received WorkerInitRequest, python version %s, "
                "worker version %s.",
                sys.version.split()[0], _worker_version())
        else:
            name = "".join(p.capitalize() for p in verb.split("_"))
            _syslog.info("Received %s.", name)
    except Exception as e:  # logging must never break dispatch
        print(f"{_CONSOLE_LOG_PREFIX} ERROR: received-log failed: {e}",
              file=sys.stderr, flush=True)


def handle_control(verb, req):
    """Run one control-plane verb. Rust prost-decodes the request into ``req``
    (a dict); we shape it for the runtime handler, run it, and return the
    response as a flat dict Rust maps back to a prost message. Returns None for
    an unknown verb."""
    msg = _build_control_message(verb, req)
    if msg is None:
        _log(f"unknown control verb: {verb!r}", level="WARNING")
        return None

    _log_control_received(verb)

    if verb == "worker_init_request":
        # The Host supplies the function app directory in the init message (not
        # via CLI). The v2 runtime imports ``function_app`` during indexing but
        # does NOT add that directory to sys.path, so do it before init runs.
        app_dir = req.get("function_app_directory", "")
        if app_dir and app_dir not in sys.path:
            sys.path.insert(0, app_dir)
            _log(f"added function_app_directory to sys.path: {app_dir!r}")
        try:
            _rt.start_threadpool_executor()
        except AttributeError:
            pass

    # worker_init / env_reload set the runtime's module-global ``protos`` from
    # properties; pass it (harmless for the other verbs, which reuse the global).
    props = {"protos": protos, "host": _host}
    req_obj = _WorkerRequest(verb, msg, props)
    handler = getattr(_rt, verb)
    try:
        resp = _run_coro(handler(req_obj))
    except Exception:  # pragma: no cover - surfaced to Rust as a log
        _log(f"{verb} handler error:\n" + traceback.format_exc(),
             level="ERROR")
        raise
    if resp is None:
        return None
    return resp.to_dict()


def handle_invocation_control(req):
    """Run an invocation on the pure-Python control path (deferred / http-v2).

    Native invocations go through ``invoke_native``; only deferred (SDK-type)
    bindings and http-v2 streaming reach here, running the runtime's standard
    ``invocation_request``. Rust passes datum tuples (see convert.rs); we rebuild
    the adapter ``ParameterBinding``/``TypedData`` inputs, run the handler, and
    return the ``InvocationResponse`` as a flat dict Rust maps to prost.
    """
    invocation_id = req.get("invocation_id", "")
    function_id = req.get("function_id", "")
    try:
        _syslog.info(
            "Received FunctionInvocationRequest, function ID %s, "
            "invocation ID %s.", function_id, invocation_id)
    except Exception:
        pass

    input_data = [
        protos.ParameterBinding(
            name=name, data=protos.TypedData.from_tuple(t))
        for name, t in (req.get("input_data") or [])
    ]
    trigger_metadata = {
        k: protos.TypedData.from_tuple(t)
        for k, t in (req.get("trigger_metadata") or {}).items()
    }

    tc = req.get("trace_context") or {}
    trace_context = SimpleNamespace(
        trace_parent=tc.get("trace_parent", ""),
        trace_state=tc.get("trace_state", ""),
        attributes=dict(tc.get("attributes") or {}))

    rc = req.get("retry_context") or {}
    exc = rc.get("exception")
    retry_context = SimpleNamespace(
        retry_count=int(rc.get("retry_count", 0)),
        max_retry_count=int(rc.get("max_retry_count", 0)),
        exception=(SimpleNamespace(**exc) if exc else
                   SimpleNamespace(message="", stack_trace="", source="")))

    invoc = SimpleNamespace(
        invocation_id=invocation_id,
        function_id=function_id,
        input_data=input_data,
        trigger_metadata=trigger_metadata,
        trace_context=trace_context,
        retry_context=retry_context)
    shim = SimpleNamespace(invocation_request=invoc)

    # The runtime reuses its module-global ``protos`` set at worker_init; the
    # dispatcher intentionally omits properties on invocations.
    req_obj = _WorkerRequest("FunctionInvocationRequest", shim)
    try:
        resp = _run_coro(_rt.invocation_request(req_obj))
    except Exception:  # pragma: no cover - surfaced to Rust as a log
        _log("invocation handler error:\n" + traceback.format_exc(),
             level="ERROR")
        raise
    if resp is None:
        return None
    return resp.to_dict()


def log_unhandled(desc):
    """Rust routes an unrecognized StreamingMessage content type here."""
    _log(f"unhandled content type: {desc}", level="WARNING")


# --- Native invocation path (no Python protobuf on the hot path) -------------
#
# Rust decodes the InvocationRequest with prost and passes us "datum tuples":
#   scalar  -> (type_str, primitive)
#   http in -> ("http", {method,url,headers,params,query,body:<datum tuple|None>})
#   empty   -> None
# We turn those into real ``Datum`` objects (the runtime's protobuf-free
# currency), run the native runtime invocation, then turn the resulting
# ``Datum`` outputs back into datum tuples for Rust to encode with prost.

_native = None
_Datum = None
_control_path_cache = {}


def requires_control_path(function_id):
    """Whether an invocation for *function_id* must take the pure-Python control
    path (``handle`` -> ``_rt.invocation_request``) instead of the native prost
    path.

    The native path (native_invocation.py) intentionally does NOT support
    deferred (SDK-type) bindings or the http-v2 streaming path; both are handled
    only by the runtime's standard ``invocation_request``. So a function is
    routed to the control path when it has deferred bindings enabled, or when it
    is an HTTP function and http-v2 streaming is enabled for the app. Result is
    cached per function_id (the answer is fixed once indexing completes).
    """
    cached = _control_path_cache.get(function_id)
    if cached is not None:
        return cached
    result = False
    try:
        import importlib
        _functions = importlib.import_module(
            f"{_rt_name}.handle_event")._functions
        fi = _functions.get_function(function_id)
        if fi is not None:
            if getattr(fi, "deferred_bindings_enabled", False):
                result = True
            elif getattr(fi, "is_http_func", False):
                # http-v2 streaming lives only in the v2 runtime; v1 has no
                # such module, so this import (and thus the control path) only
                # ever triggers for v2 apps.
                try:
                    http_v2 = importlib.import_module(f"{_rt_name}.http_v2")
                    if http_v2.HttpV2Registry.http_v2_enabled():
                        result = True
                except ImportError:
                    pass
    except Exception as e:
        _log(f"requires_control_path check failed for {function_id!r}: {e}",
             level="WARNING")
        result = False
    _control_path_cache[function_id] = result
    return result


def _ensure_native():
    """Lazily import the selected runtime's native invocation entry + Datum type.

    Safe to call only after worker_init (which populates the runtime's function
    registry via the pure-Python control path in ``handle``). Resolves against
    the runtime chosen in ``configure`` (v2 ``azure_functions_runtime`` or v1
    ``azure_functions_runtime_v1``), so v1 apps get the native fast path too."""
    global _native, _Datum
    if _native is None:
        import importlib
        _native = importlib.import_module(f"{_rt_name}.native_invocation")
        _Datum = importlib.import_module(
            f"{_rt_name}.bindings.datumdef").Datum
    return _native


def _tuple_to_datum(t):
    """datum tuple (from Rust) -> runtime ``Datum`` (nested for http input)."""
    if t is None:
        return None
    type_str, value = t
    if type_str == 'http':
        body = value.get('body')
        return _Datum(dict(
            method=_Datum(value.get('method'), 'string'),
            url=_Datum(value.get('url'), 'string'),
            headers={k: _Datum(v, 'string')
                     for k, v in (value.get('headers') or {}).items()},
            params={k: _Datum(v, 'string')
                    for k, v in (value.get('params') or {}).items()},
            query={k: _Datum(v, 'string')
                   for k, v in (value.get('query') or {}).items()},
            body=(_tuple_to_datum(body) or _Datum(b'', 'bytes')),
        ), 'http')
    return _Datum(value, type_str)


def _datum_to_tuple(d):
    """runtime ``Datum`` -> datum tuple (for Rust to prost-encode)."""
    if d is None:
        return None
    if d.type == 'http':
        v = d.value
        if v.get('cookies'):
            raise NotImplementedError(
                "native path: http cookies not supported")
        return ('http', {
            'status_code': str(v['status_code'].value),
            'headers': {k: str(hv.value) for k, hv in v['headers'].items()},
            'body': _datum_to_tuple(v['body']),
        })
    return (d.type, d.value)


def invoke_native(function_id, invocation_id, inputs, trigger_metadata):
    """Entry called by Rust for the native invocation hot path.

    Returns ``(ok, return_datum_tuple, output_data_tuples, exception_text)``.
    """
    ni = _ensure_native()
    if not getattr(invoke_native, "_marked", False):
        _log("NATIVE-INVOKE-PATH active (prost in Rust, no Python protobuf on "
             "the invocation hot path)")
        invoke_native._marked = True
    # Per-invocation System log (parity with the proxy worker's
    # `Received FunctionInvocationRequest`). The invocation travels the native
    # prost path, so it never reaches _dispatch -- log it here.
    try:
        _syslog.info(
            "Received FunctionInvocationRequest, function ID %s, "
            "invocation ID %s.", function_id, invocation_id)
    except Exception:
        pass
    in_datums = [(name, _tuple_to_datum(t)) for name, t in inputs]
    meta = {k: _tuple_to_datum(t)
            for k, t in (trigger_metadata or {}).items()}
    # Prefer the synchronous native path: it runs the handler directly on THIS
    # (Rust-dispatched) thread with no event-loop funnel. async handlers are
    # not "handled" here and fall through to the single-loop coroutine path.
    handled, ok, ret, outputs, exc = ni.run_invocation_sync(
        invocation_id, function_id, in_datums, meta)
    if not handled:
        ok, ret, outputs, exc = _run_coro(
            ni.invocation_request_native(
                invocation_id, function_id, in_datums, meta))
    if not ok:
        return (False, None, [], exc)
    ret_tuple = _datum_to_tuple(ret)
    out_tuples = [(name, _datum_to_tuple(d)) for name, d in outputs]
    return (True, ret_tuple, out_tuples, None)


def shutdown():
    try:
        if _rt is not None:
            _rt.stop_threadpool_executor()
    except Exception:
        pass
    if _loop is not None:
        _loop.call_soon_threadsafe(_loop.stop)
