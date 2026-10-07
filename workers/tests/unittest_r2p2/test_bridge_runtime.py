# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import contextvars
import importlib
import logging
import sys
import threading
from types import ModuleType, SimpleNamespace

import pytest

import bridge


class _Sink:
    def __init__(self):
        self.fields = []

    def emit_log(self, fields):
        self.fields.append(fields)


@pytest.fixture
def reset_bridge_state(monkeypatch):
    names = (
        "_rt", "_rt_tls", "_host", "_function_app_directory",
        "_workers_dir", "_log_sink", "_request_id", "_worker_id",
        "_loop", "_loop_thread", "_native", "_Datum",
    )
    original = {name: getattr(bridge, name) for name in names}
    original_runtime_name = bridge._rt_name
    original_logging_installed = bridge._rpc_logging_installed
    original_cache = bridge._control_path_cache
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield
    if bridge._loop is not None and bridge._loop is not original["_loop"]:
        bridge._loop.call_soon_threadsafe(bridge._loop.stop)
        thread = bridge._loop_thread
        if thread is not None:
            thread.join(timeout=2)
        bridge._loop.close()
    for name, value in original.items():
        monkeypatch.setattr(bridge, name, value)
    monkeypatch.setattr(bridge, "_rt_name", original_runtime_name)
    monkeypatch.setattr(
        bridge, "_rpc_logging_installed", original_logging_installed)
    monkeypatch.setattr(bridge, "_control_path_cache", original_cache)
    root.handlers[:] = original_handlers
    root.setLevel(original_level)


def test_console_log_selects_stream_and_format(capsys):
    bridge._log("started")
    bridge._log("failed", level="ERROR")

    captured = capsys.readouterr()
    assert captured.out == "LanguageWorkerConsoleLog INFO: started\n"
    assert captured.err == "LanguageWorkerConsoleLog ERROR: failed\n"


def test_current_invocation_id_prefers_contextvar_then_thread_local(
        monkeypatch):
    invocation_id = contextvars.ContextVar("invocation_id", default=None)
    token = invocation_id.set("context-id")
    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(invocation_id_cv=invocation_id))
    monkeypatch.setattr(
        bridge, "_rt_tls", SimpleNamespace(invocation_id="thread-id"))

    assert bridge._current_invocation_id() == "context-id"
    invocation_id.reset(token)
    assert bridge._current_invocation_id() == "thread-id"


def test_current_invocation_id_tolerates_runtime_access_errors(monkeypatch):
    class _Broken:
        def get(self):
            raise RuntimeError("context unavailable")

    class _BrokenTls:
        @property
        def invocation_id(self):
            raise RuntimeError("thread local unavailable")

    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(invocation_id_cv=_Broken()))
    monkeypatch.setattr(bridge, "_rt_tls", _BrokenTls())

    assert bridge._current_invocation_id() is None


def test_current_invocation_id_without_runtime_state(monkeypatch):
    monkeypatch.setattr(bridge, "_rt", None)
    monkeypatch.setattr(bridge, "_rt_tls", None)

    assert bridge._current_invocation_id() is None

    monkeypatch.setattr(
        bridge, "_rt_tls", SimpleNamespace(invocation_id=None))
    assert bridge._current_invocation_id() is None


def test_rpc_log_handler_emits_user_and_system_fields(monkeypatch):
    sink = _Sink()
    monkeypatch.setattr(bridge, "_log_sink", sink)
    monkeypatch.setattr(bridge, "_current_invocation_id", lambda: "inv-1")
    handler = bridge._RpcLogHandler()
    handler.setFormatter(logging.Formatter("prefix: %(message)s"))

    handler.emit(logging.LogRecord(
        "customer.module", logging.WARNING, __file__, 1, "hello", (), None))
    handler.emit(logging.LogRecord(
        "azure_functions_runtime.worker", logging.ERROR,
        __file__, 1, "failed", (), None))

    assert sink.fields == [
        {
            "level": bridge._LOG_LEVEL_WARNING,
            "message": "prefix: hello",
            "category": "customer.module",
            "log_category": bridge._LOG_CATEGORY_USER,
            "invocation_id": "inv-1",
        },
        {
            "level": bridge._LOG_LEVEL_ERROR,
            "message": "prefix: failed",
            "category": "azure_functions_runtime.worker",
            "log_category": bridge._LOG_CATEGORY_SYSTEM,
            "invocation_id": "inv-1",
        },
    ]


def test_rpc_log_handler_ignores_missing_sink_and_never_raises(
        monkeypatch, capsys):
    handler = bridge._RpcLogHandler()
    monkeypatch.setattr(bridge, "_log_sink", None)
    handler.emit(logging.LogRecord(
        "customer", logging.INFO, __file__, 1, "ignored", (), None))

    class _BrokenSink:
        def emit_log(self, fields):
            raise RuntimeError("sink closed")

    monkeypatch.setattr(bridge, "_log_sink", _BrokenSink())
    handler.emit(logging.LogRecord(
        "customer", logging.INFO, __file__, 1, "message", (), None))

    assert "rpc-log emit failed: sink closed" in capsys.readouterr().err


def test_install_rpc_logging_is_idempotent_and_honors_debug(monkeypatch):
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    sink = _Sink()
    monkeypatch.setattr(bridge, "_log_sink", sink)
    monkeypatch.setattr(bridge, "_rpc_logging_installed", False)
    monkeypatch.setenv("PYTHON_ENABLE_DEBUG_LOGGING", "true")
    try:
        bridge._install_rpc_logging()
        added = [h for h in root.handlers if h not in original_handlers]
        bridge._install_rpc_logging()

        assert root.level == logging.DEBUG
        assert len(added) == 1
        assert isinstance(added[0], bridge._RpcLogHandler)
        assert root.handlers.count(added[0]) == 1
    finally:
        root.handlers[:] = original_handlers
        root.setLevel(original_level)


def test_install_rpc_logging_requires_sink(monkeypatch):
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    monkeypatch.setattr(bridge, "_log_sink", None)
    monkeypatch.setattr(bridge, "_rpc_logging_installed", False)

    bridge._install_rpc_logging()

    assert root.handlers == original_handlers
    assert not bridge._rpc_logging_installed


def test_dispatch_logging_helpers_never_raise(monkeypatch, capsys):
    class _BrokenLogger:
        def info(self, *args):
            raise RuntimeError("logger unavailable")

    monkeypatch.setattr(bridge, "_syslog", _BrokenLogger())

    bridge._log_using_library()
    bridge._log_control_received("functions_metadata_request", {})

    assert "received-log failed: logger unavailable" in capsys.readouterr().err


def test_bridge_loop_runs_coroutines_and_shutdown_stops_runtime(
        monkeypatch, reset_bridge_state):
    calls = []
    runtime = SimpleNamespace(
        stop_threadpool_executor=lambda: calls.append("stop"))
    monkeypatch.setattr(bridge, "_rt", runtime)
    monkeypatch.setattr(bridge, "_loop", None)
    monkeypatch.setattr(bridge, "_loop_thread", None)

    bridge._start_loop()
    first_loop = bridge._loop
    bridge._start_loop()

    async def value():
        return 42

    assert bridge._loop is first_loop
    assert bridge._run_coro(value()) == 42
    bridge.shutdown()
    bridge._loop_thread.join(timeout=2)
    assert calls == ["stop"]
    assert not bridge._loop_thread.is_alive()


def test_shutdown_tolerates_missing_state_and_runtime_error(monkeypatch):
    def fail_stop():
        raise RuntimeError("executor unavailable")

    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(stop_threadpool_executor=fail_stop))
    monkeypatch.setattr(bridge, "_loop", None)
    bridge.shutdown()

    monkeypatch.setattr(bridge, "_rt", None)
    bridge.shutdown()


def _runtime_module(name):
    runtime = ModuleType(name)
    runtime.version = SimpleNamespace(VERSION="9.9.9")
    runtime.invocation_id_cv = contextvars.ContextVar(
        f"{name}_invocation_id", default=None)
    return runtime


@pytest.mark.parametrize(
    ("has_v2_script", "runtime_name"),
    ((True, "azure_functions_runtime"),
     (False, "azure_functions_runtime_v1")),
)
def test_configure_selects_runtime_and_sets_bridge_state(
        monkeypatch, tmp_path, has_v2_script, runtime_name,
        reset_bridge_state):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    if has_v2_script:
        app_dir.joinpath("function_app.py").write_text("", encoding="utf-8")
    runtime = _runtime_module(runtime_name)
    context = ModuleType(f"{runtime_name}.bindings.context")
    context._invocation_id_local = threading.local()
    monkeypatch.setitem(sys.modules, runtime_name, runtime)
    monkeypatch.setitem(sys.modules, context.__name__, context)
    calls = []
    monkeypatch.setattr(
        bridge, "_prioritize_customer_dependencies",
        lambda directory: calls.append(("priority", directory)) or "cx-deps")
    monkeypatch.setattr(bridge, "_start_loop", lambda: calls.append("loop"))
    monkeypatch.setattr(
        bridge, "_install_rpc_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO":
        calls.append(("log", level, message)))
    sink = _Sink()

    bridge.configure(
        "workers-dir", str(app_dir), "localhost", "request-1", sink,
        "worker-1")

    assert bridge._rt is runtime
    assert bridge._rt_name == runtime_name
    assert bridge._rt_tls is context._invocation_id_local
    assert bridge._host == "localhost"
    assert bridge._function_app_directory == str(app_dir)
    assert bridge._workers_dir == "workers-dir"
    assert bridge._log_sink is sink
    assert bridge._request_id == "request-1"
    assert bridge._worker_id == "worker-1"
    assert calls[:3] == [("priority", str(app_dir)), "loop", "logging"]
    assert "cx_deps='cx-deps'" in calls[3][2]


def test_configure_uses_custom_script_name_and_tolerates_missing_tls(
        monkeypatch, tmp_path, reset_bridge_state):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    app_dir.joinpath("custom.py").write_text("", encoding="utf-8")
    runtime = _runtime_module("azure_functions_runtime")
    monkeypatch.setitem(sys.modules, "azure_functions_runtime", runtime)
    monkeypatch.setenv("PYTHON_SCRIPT_FILE_NAME", "custom.py")
    monkeypatch.setattr(
        bridge, "_prioritize_customer_dependencies", lambda directory: "")
    monkeypatch.setattr(bridge, "_start_loop", lambda: None)
    monkeypatch.setattr(bridge, "_install_rpc_logging", lambda: None)
    real_import_module = importlib.import_module

    def fail_context_import(name):
        if name.endswith(".bindings.context"):
            raise ImportError("missing context")
        return real_import_module(name)

    monkeypatch.setattr(importlib, "import_module", fail_context_import)
    messages = []
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO":
        messages.append((level, message)))

    bridge.configure("", str(app_dir), None)

    assert bridge._rt is runtime
    assert bridge._rt_name == "azure_functions_runtime"
    assert bridge._rt_tls is None
    assert bridge._host == ""
    assert bridge._request_id == ""
    assert bridge._worker_id == ""
    assert any("could not cache runtime thread-local" in message
               for _, message in messages)


class _Response:
    def __init__(self, value):
        self.value = value

    def to_dict(self):
        return self.value


def test_handle_control_worker_init_shapes_request_and_response(
        monkeypatch, tmp_path):
    captured = {}

    def start_threadpool_executor():
        captured["started"] = True

    def worker_init_request(request):
        captured["request"] = request
        return "worker-init-token"

    monkeypatch.setattr(bridge, "_rt", SimpleNamespace(
        version=SimpleNamespace(VERSION="1.2.3"),
        start_threadpool_executor=start_threadpool_executor,
        worker_init_request=worker_init_request))
    monkeypatch.setattr(bridge, "_host", "localhost")
    monkeypatch.setattr(
        bridge, "_run_coro",
        lambda token: _Response({"kind": token}))
    monkeypatch.setattr(bridge, "_log_control_received", lambda *args: None)
    monkeypatch.setattr(bridge, "_log_using_library", lambda: None)
    app_dir = str(tmp_path / "app")
    original_path = list(sys.path)
    try:
        result = bridge.handle_control("worker_init_request", {
            "function_app_directory": app_dir,
            "capabilities": {"A": "true"},
            "host_version": "4.0.0",
        })
    finally:
        sys.path[:] = original_path

    request = captured["request"]
    assert captured["started"]
    assert request.name == "worker_init_request"
    assert request.request.worker_init_request.capabilities == {"A": "true"}
    assert request.properties == {
        "protos": bridge.protos, "host": "localhost"}
    assert result == {"kind": "worker-init-token"}


def test_handle_control_worker_init_allows_runtime_without_threadpool(
        monkeypatch):
    runtime = SimpleNamespace(worker_init_request=lambda request: "token")
    monkeypatch.setattr(bridge, "_rt", runtime)
    monkeypatch.setattr(bridge, "_run_coro", lambda token: _Response({}))
    monkeypatch.setattr(bridge, "_log_control_received", lambda *args: None)
    monkeypatch.setattr(bridge, "_log_using_library", lambda: None)

    assert bridge.handle_control("worker_init_request", {}) == {}


def test_handle_control_reload_reprioritizes_and_none_response(monkeypatch):
    calls = []
    runtime = SimpleNamespace(
        function_environment_reload_request=lambda request: "reload-token")
    monkeypatch.setattr(bridge, "_rt", runtime)
    monkeypatch.setattr(
        bridge, "_prioritize_customer_dependencies",
        lambda directory: calls.append(("priority", directory)))
    monkeypatch.setattr(
        bridge, "_select_runtime",
        lambda directory: calls.append(("runtime", directory)))
    monkeypatch.setattr(
        bridge, "_log_using_library", lambda: calls.append("library"))
    monkeypatch.setattr(bridge, "_log_control_received", lambda *args: None)
    monkeypatch.setattr(bridge, "_run_coro", lambda token: None)

    result = bridge.handle_control(
        "function_environment_reload_request",
        {"function_app_directory": "/specialized"})

    assert result is None
    assert calls == [
        ("priority", "/specialized"),
        ("runtime", "/specialized"),
        "library",
    ]


def test_handle_control_reload_switches_placeholder_runtime(
        monkeypatch, tmp_path, reset_bridge_state):
    placeholder_dir = tmp_path / "placeholder"
    placeholder_dir.mkdir()
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    app_dir.joinpath("function_app.py").write_text("", encoding="utf-8")

    calls = []
    v1_runtime = _runtime_module("azure_functions_runtime_v1")
    v1_runtime.stop_threadpool_executor = (
        lambda: calls.append("v1-threadpool-stop"))
    v1_runtime.function_environment_reload_request = (
        lambda request: calls.append("v1-reload") or "v1-reload")
    v1_runtime.functions_metadata_request = (
        lambda request: "v1-metadata")
    v2_runtime = _runtime_module("azure_functions_runtime")
    v2_runtime.start_threadpool_executor = (
        lambda: calls.append("v2-threadpool"))
    v2_runtime.function_environment_reload_request = (
        lambda request: calls.append("v2-reload") or "v2-reload")
    v2_runtime.functions_metadata_request = (
        lambda request: "v2-metadata")
    monkeypatch.setitem(sys.modules, v1_runtime.__name__, v1_runtime)
    monkeypatch.setitem(sys.modules, v2_runtime.__name__, v2_runtime)
    contexts = {}
    for runtime_name in (v1_runtime.__name__, v2_runtime.__name__):
        context = ModuleType(f"{runtime_name}.bindings.context")
        context._invocation_id_local = threading.local()
        contexts[runtime_name] = context
        monkeypatch.setitem(sys.modules, context.__name__, context)

    monkeypatch.setattr(
        bridge, "_prioritize_customer_dependencies", lambda directory: "")
    monkeypatch.setattr(bridge, "_start_loop", lambda: None)
    monkeypatch.setattr(bridge, "_install_rpc_logging", lambda: None)
    monkeypatch.setattr(bridge, "_log_control_received", lambda *args: None)
    monkeypatch.setattr(bridge, "_log_using_library", lambda: None)
    monkeypatch.setattr(
        bridge, "_run_coro", lambda token: _Response({"kind": token}))

    bridge.configure("", str(placeholder_dir), None)
    assert bridge._rt_name == "azure_functions_runtime_v1"
    stale_native = object()
    stale_datum = object()
    monkeypatch.setattr(bridge, "_native", stale_native)
    monkeypatch.setattr(bridge, "_Datum", stale_datum)
    monkeypatch.setattr(bridge, "_control_path_cache", {"old-id": True})

    reload_response = bridge.handle_control(
        "function_environment_reload_request",
        {"function_app_directory": str(app_dir)})
    metadata_response = bridge.handle_control(
        "functions_metadata_request", {})

    assert reload_response == {"kind": "v2-reload"}
    assert metadata_response == {"kind": "v2-metadata"}
    assert calls == [
        "v1-threadpool-stop", "v2-reload", "v2-threadpool"]
    assert bridge._rt is v2_runtime
    assert bridge._rt_name == "azure_functions_runtime"
    assert bridge._rt_tls is contexts[
        "azure_functions_runtime"]._invocation_id_local
    assert bridge._function_app_directory == str(app_dir)
    assert bridge._native is None
    assert bridge._Datum is None
    assert bridge._control_path_cache == {}


def test_handle_control_unknown_and_handler_error(monkeypatch):
    logs = []
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO":
        logs.append((level, message)))

    assert bridge.handle_control("unknown_request", {}) is None
    assert logs == [("WARNING", "unknown control request: 'unknown_request'")]

    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(
            functions_metadata_request=lambda request: "token"))
    monkeypatch.setattr(bridge, "_log_control_received", lambda *args: None)
    monkeypatch.setattr(
        bridge, "_run_coro",
        lambda token: (_ for _ in ()).throw(RuntimeError("handler failed")))

    with pytest.raises(RuntimeError, match="handler failed"):
        bridge.handle_control("functions_metadata_request", {})
    assert logs[-1][0] == "ERROR"
    assert "functions_metadata_request handler error" in logs[-1][1]


def test_log_unhandled_emits_warning(monkeypatch):
    calls = []
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO":
        calls.append((message, level)))

    bridge.log_unhandled("InvocationCancel")

    assert calls == [("unhandled content type: InvocationCancel", "WARNING")]
