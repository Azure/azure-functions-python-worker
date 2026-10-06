# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import importlib
from http.cookies import SimpleCookie
from types import SimpleNamespace

import pytest

import bridge


class _Response:
    def __init__(self, value):
        self.value = value

    def to_dict(self):
        return self.value


class _Datum:
    def __init__(self, value, type):
        self.value = value
        self.type = type


def test_handle_invocation_control_builds_runtime_request(monkeypatch):
    captured = {}

    def invocation_request(request):
        captured["request"] = request
        return "invocation-token"

    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(invocation_request=invocation_request))
    monkeypatch.setattr(
        bridge, "_run_coro",
        lambda token: _Response({"token": token}))
    monkeypatch.setattr(bridge, "_request_id", "request-1")
    monkeypatch.setattr(bridge, "_worker_id", "worker-1")

    result = bridge.handle_invocation_control({
        "invocation_id": "inv-1",
        "function_id": "fid-1",
        "input_data": [
            ("req", ("string", "body")),
            ("empty", None),
        ],
        "trigger_metadata": {"meta": ("int", 7)},
        "trace_context": {
            "trace_parent": "trace-parent",
            "trace_state": "trace-state",
            "attributes": {"key": "value"},
        },
        "retry_context": {
            "retry_count": 2,
            "max_retry_count": 5,
            "exception": {
                "message": "retry", "stack_trace": "stack",
                "source": "host"},
        },
    })

    request = captured["request"]
    invocation = request.request.invocation_request
    assert request.name == "FunctionInvocationRequest"
    assert request.properties is None
    assert invocation.invocation_id == "inv-1"
    assert invocation.function_id == "fid-1"
    assert invocation.input_data[0].name == "req"
    assert invocation.input_data[0].data.to_dict() == ("string", "body")
    assert invocation.input_data[1].data.to_dict() is None
    assert invocation.trigger_metadata["meta"].to_dict() == ("int", 7)
    assert invocation.trace_context.trace_parent == "trace-parent"
    assert invocation.trace_context.trace_state == "trace-state"
    assert invocation.trace_context.attributes == {"key": "value"}
    assert invocation.retry_context.retry_count == 2
    assert invocation.retry_context.max_retry_count == 5
    assert invocation.retry_context.exception.message == "retry"
    assert result == {"token": "invocation-token"}


def test_handle_invocation_control_defaults_and_none_response(monkeypatch):
    captured = {}

    def invocation_request(request):
        captured["request"] = request
        return "token"

    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(invocation_request=invocation_request))
    monkeypatch.setattr(bridge, "_run_coro", lambda token: None)

    assert bridge.handle_invocation_control({}) is None
    invocation = captured["request"].request.invocation_request
    assert invocation.invocation_id == ""
    assert invocation.function_id == ""
    assert invocation.input_data == []
    assert invocation.trigger_metadata == {}
    assert invocation.trace_context.trace_parent == ""
    assert invocation.trace_context.trace_state == ""
    assert invocation.trace_context.attributes == {}
    assert invocation.retry_context.retry_count == 0
    assert invocation.retry_context.max_retry_count == 0
    assert invocation.retry_context.exception.message == ""


def test_handle_invocation_control_tolerates_request_log_error(monkeypatch):
    class _BrokenLogger:
        def info(self, *args):
            raise RuntimeError("logger unavailable")

    monkeypatch.setattr(bridge, "_syslog", _BrokenLogger())
    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(
            invocation_request=lambda request: "token"))
    monkeypatch.setattr(bridge, "_run_coro", lambda token: None)

    assert bridge.handle_invocation_control({}) is None


def test_handle_invocation_control_logs_and_reraises_handler_error(monkeypatch):
    logs = []
    monkeypatch.setattr(
        bridge, "_rt", SimpleNamespace(
            invocation_request=lambda request: "token"))
    monkeypatch.setattr(
        bridge, "_run_coro",
        lambda token: (_ for _ in ()).throw(RuntimeError("invoke failed")))
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO":
        logs.append((level, message)))

    with pytest.raises(RuntimeError, match="invoke failed"):
        bridge.handle_invocation_control({})

    assert logs[-1][0] == "ERROR"
    assert "invocation handler error" in logs[-1][1]


class _Functions:
    def __init__(self, function):
        self.function = function
        self.calls = []

    def get_function(self, function_id):
        self.calls.append(function_id)
        return self.function


def test_requires_control_path_for_deferred_binding_and_caches(monkeypatch):
    functions = _Functions(SimpleNamespace(
        deferred_bindings_enabled=True, is_http_func=False))
    handle_event = SimpleNamespace(_functions=functions)
    imports = []

    def import_module(name):
        imports.append(name)
        assert name == "azure_functions_runtime.handle_event"
        return handle_event

    monkeypatch.setattr(importlib, "import_module", import_module)
    monkeypatch.setattr(bridge, "_rt_name", "azure_functions_runtime")
    monkeypatch.setattr(bridge, "_control_path_cache", {})

    assert bridge.requires_control_path("fid")
    assert bridge.requires_control_path("fid")
    assert functions.calls == ["fid"]
    assert imports == ["azure_functions_runtime.handle_event"]


def test_requires_control_path_for_http_v2_and_native_cases(monkeypatch):
    functions = _Functions(SimpleNamespace(
        deferred_bindings_enabled=False, is_http_func=True))
    handle_event = SimpleNamespace(_functions=functions)
    http_v2 = SimpleNamespace(HttpV2Registry=SimpleNamespace(
        http_v2_enabled=lambda: True))

    def import_module(name):
        if name.endswith(".handle_event"):
            return handle_event
        if name.endswith(".http_v2"):
            return http_v2
        raise AssertionError(name)

    monkeypatch.setattr(importlib, "import_module", import_module)
    monkeypatch.setattr(bridge, "_control_path_cache", {})
    assert bridge.requires_control_path("http-fid")

    functions.function = None
    assert not bridge.requires_control_path("missing-fid")


def test_requires_control_path_caches_false_and_http_v2_disabled(monkeypatch):
    monkeypatch.setattr(bridge, "_control_path_cache", {"cached": False})
    monkeypatch.setattr(
        importlib, "import_module",
        lambda name: (_ for _ in ()).throw(AssertionError(name)))
    assert not bridge.requires_control_path("cached")

    functions = _Functions(SimpleNamespace(
        deferred_bindings_enabled=False, is_http_func=True))

    def import_module(name):
        if name.endswith(".handle_event"):
            return SimpleNamespace(_functions=functions)
        if name.endswith(".http_v2"):
            return SimpleNamespace(HttpV2Registry=SimpleNamespace(
                http_v2_enabled=lambda: False))
        raise AssertionError(name)

    monkeypatch.setattr(importlib, "import_module", import_module)
    monkeypatch.setattr(bridge, "_control_path_cache", {})
    assert not bridge.requires_control_path("http-disabled")

    functions.function = SimpleNamespace(
        deferred_bindings_enabled=False, is_http_func=False)
    assert not bridge.requires_control_path("native")


def test_requires_control_path_handles_missing_http_v2_and_lookup_errors(
        monkeypatch):
    functions = _Functions(SimpleNamespace(
        deferred_bindings_enabled=False, is_http_func=True))
    handle_event = SimpleNamespace(_functions=functions)

    def import_without_http_v2(name):
        if name.endswith(".handle_event"):
            return handle_event
        raise ImportError("v1 has no http_v2")

    monkeypatch.setattr(importlib, "import_module", import_without_http_v2)
    monkeypatch.setattr(bridge, "_control_path_cache", {})
    assert not bridge.requires_control_path("v1-http")

    logs = []
    monkeypatch.setattr(
        importlib, "import_module",
        lambda name: (_ for _ in ()).throw(RuntimeError("registry failed")))
    monkeypatch.setattr(bridge, "_control_path_cache", {})
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO":
        logs.append((level, message)))
    assert not bridge.requires_control_path("broken")
    assert logs == [(
        "WARNING",
        "requires_control_path check failed for 'broken': registry failed")]


def test_ensure_native_lazily_imports_selected_runtime(monkeypatch):
    native = SimpleNamespace(name="native")
    datum_type = type("RuntimeDatum", (), {})
    imports = []

    def import_module(name):
        imports.append(name)
        if name == "azure_functions_runtime_v1.native_invocation":
            return native
        if name == "azure_functions_runtime_v1.bindings.datumdef":
            return SimpleNamespace(Datum=datum_type)
        raise AssertionError(name)

    monkeypatch.setattr(importlib, "import_module", import_module)
    monkeypatch.setattr(bridge, "_rt_name", "azure_functions_runtime_v1")
    monkeypatch.setattr(bridge, "_native", None)
    monkeypatch.setattr(bridge, "_Datum", None)

    assert bridge._ensure_native() is native
    assert bridge._ensure_native() is native
    assert bridge._Datum is datum_type
    assert imports == [
        "azure_functions_runtime_v1.native_invocation",
        "azure_functions_runtime_v1.bindings.datumdef",
    ]


def test_tuple_to_datum_supports_none_scalar_and_http(monkeypatch):
    monkeypatch.setattr(bridge, "_Datum", _Datum)

    assert bridge._tuple_to_datum(None) is None
    scalar = bridge._tuple_to_datum(("json", '{"ok": true}'))
    assert scalar.type == "json"
    assert scalar.value == '{"ok": true}'

    http = bridge._tuple_to_datum(("http", {
        "method": "POST",
        "url": "https://example.test/api",
        "headers": {"content-type": "text/plain"},
        "params": {"route": "value"},
        "query": {"q": "search"},
        "body": None,
    }))
    assert http.type == "http"
    assert http.value["method"].value == "POST"
    assert http.value["url"].value == "https://example.test/api"
    assert http.value["headers"]["content-type"].value == "text/plain"
    assert http.value["params"]["route"].value == "value"
    assert http.value["query"]["q"].value == "search"
    assert http.value["body"].type == "bytes"
    assert http.value["body"].value == b""


def _cookie(name, same_site="", expires="", max_age=""):
    cookie = SimpleCookie()
    cookie[name] = "value"
    morsel = cookie[name]
    morsel["domain"] = "example.com"
    morsel["path"] = "/api"
    morsel["secure"] = True
    morsel["httponly"] = True
    morsel["samesite"] = same_site
    morsel["expires"] = expires
    morsel["max-age"] = max_age
    return cookie


def test_flatten_cookies_maps_same_site_times_and_invalid_values():
    cookies = [
        _cookie("lax", "Lax", "Wed, 01 Jan 2025 00:00:00 GMT", "30"),
        _cookie("strict", "Strict"),
        _cookie("explicit", "none"),
        _cookie("default", "unknown", "not-a-date", "not-a-number"),
    ]

    flattened = bridge._flatten_cookies(cookies)

    assert [item["same_site"] for item in flattened] == [1, 2, 3, 0]
    assert flattened[0]["expires"] is not None
    assert flattened[0]["max_age"] == 30.0
    assert flattened[0]["domain"] == "example.com"
    assert flattened[0]["path"] == "/api"
    assert flattened[0]["secure"] is True
    assert flattened[0]["http_only"] is True
    assert flattened[3]["expires"] is None
    assert flattened[3]["max_age"] is None
    assert bridge._flatten_cookies(None) == []


def test_datum_to_tuple_flattens_http_outputs(monkeypatch):
    cookie = _cookie("session", "Strict")
    datum = _Datum({
        "status_code": _Datum(202, "int"),
        "headers": {"x-value": _Datum(5, "int")},
        "cookies": [cookie],
        "body": _Datum(b"accepted", "bytes"),
    }, "http")

    result = bridge._datum_to_tuple(datum)

    assert result[0] == "http"
    assert result[1]["status_code"] == "202"
    assert result[1]["headers"] == {"x-value": "5"}
    assert result[1]["cookies"][0]["name"] == "session"
    assert result[1]["body"] == ("bytes", b"accepted")
    assert bridge._datum_to_tuple(None) is None
    assert bridge._datum_to_tuple(_Datum("value", "string")) == (
        "string", "value")


def test_invoke_native_sync_success_converts_inputs_outputs_and_marks_once(
        monkeypatch):
    captured = {}

    def run_invocation_sync(*args):
        captured["args"] = args
        return (
            True, True, _Datum("return", "string"),
            [("output", _Datum(42, "int"))], None)

    native = SimpleNamespace(run_invocation_sync=run_invocation_sync)
    logs = []
    monkeypatch.setattr(bridge, "_ensure_native", lambda: native)
    monkeypatch.setattr(bridge, "_Datum", _Datum)
    monkeypatch.delattr(bridge.invoke_native, "_marked", raising=False)
    monkeypatch.setattr(
        bridge, "_log", lambda message, level="INFO": logs.append(message))

    result = bridge.invoke_native(
        "fid", "inv", [("input", ("string", "value"))],
        {"meta": ("int", 7)})
    bridge.invoke_native("fid", "inv-2", [], {})

    assert result == (
        True, ("string", "return"), [("output", ("int", 42))], None)
    args = captured["args"]
    assert args[:2] == ("inv-2", "fid")
    assert logs == [
        "NATIVE-INVOKE-PATH active (prost in Rust, no Python protobuf on "
        "the invocation hot path)"]


def test_invoke_native_sync_failure_returns_exception(monkeypatch):
    native = SimpleNamespace(run_invocation_sync=lambda *args: (
        True, False, None, [], "user failure"))
    monkeypatch.setattr(bridge, "_ensure_native", lambda: native)

    assert bridge.invoke_native("fid", "inv", [], {}) == (
        False, None, [], "user failure")


def test_invoke_native_forwards_retry_exception_and_tolerates_log_error(
        monkeypatch):
    captured = {}

    class _BrokenLogger:
        def info(self, *args):
            raise RuntimeError("logger unavailable")

    def run_invocation_sync(*args):
        captured["args"] = args
        return (True, True, None, [], None)

    monkeypatch.setattr(
        bridge, "_ensure_native",
        lambda: SimpleNamespace(run_invocation_sync=run_invocation_sync))
    monkeypatch.setattr(bridge, "_syslog", _BrokenLogger())

    result = bridge.invoke_native("fid", "inv", [], {}, retry_context={
        "retry_count": "2",
        "max_retry_count": "4",
        "exception": {
            "message": "retry message",
            "stack_trace": "retry stack",
            "source": "host",
            "type": "RetryError",
        },
    })

    assert result == (True, None, [], None)
    assert captured["args"][6:8] == (2, 4)
    retry_exception = captured["args"][8]
    assert retry_exception.message == "retry message"
    assert retry_exception.stack_trace == "retry stack"
    assert retry_exception.source == "host"
    assert retry_exception.type == "RetryError"


def test_invoke_native_falls_back_to_async_runtime(monkeypatch):
    captured = {}

    def invocation_request_native(*args):
        captured["async_args"] = args
        return "async-token"

    native = SimpleNamespace(
        run_invocation_sync=lambda *args: (False, False, None, [], None),
        invocation_request_native=invocation_request_native)
    monkeypatch.setattr(bridge, "_ensure_native", lambda: native)
    monkeypatch.setattr(bridge, "_Datum", _Datum)
    monkeypatch.setattr(
        bridge, "_run_coro",
        lambda token: (True, _Datum("async", "string"), [], None))

    result = bridge.invoke_native(
        "fid", "inv", [], {}, "trace-parent", "trace-state")

    assert result == (True, ("string", "async"), [], None)
    assert captured["async_args"][:6] == (
        "inv", "fid", [], {}, "trace-parent", "trace-state")
