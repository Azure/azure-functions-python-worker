# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Small pure-function tests: log-level mapping, System-vs-User category routing,
# and the worker version fallback. These mirror proxy_worker/logging.py behavior
# the R2P2 bridge reproduces.

import logging
from types import SimpleNamespace

import bridge


def test_level_to_rpc_mapping():
    assert bridge._level_to_rpc(logging.CRITICAL) == bridge._LOG_LEVEL_CRITICAL
    assert bridge._level_to_rpc(logging.ERROR) == bridge._LOG_LEVEL_ERROR
    assert bridge._level_to_rpc(logging.WARNING) == bridge._LOG_LEVEL_WARNING
    assert bridge._level_to_rpc(logging.INFO) == bridge._LOG_LEVEL_INFO
    assert bridge._level_to_rpc(logging.DEBUG) == bridge._LOG_LEVEL_DEBUG
    # Below DEBUG still maps to the lowest (Debug) level.
    assert bridge._level_to_rpc(1) == bridge._LOG_LEVEL_DEBUG


def test_is_system_log_category():
    assert bridge._is_system_log_category("azure_functions_runtime")
    assert bridge._is_system_log_category("azure_functions_runtime.dispatcher")
    assert bridge._is_system_log_category("azure.functions")
    assert bridge._is_system_log_category("azure.functions.something")
    # Customer code logs (root or their own names) are User logs.
    assert not bridge._is_system_log_category("root")
    assert not bridge._is_system_log_category("my_app.module")


def test_worker_version_unknown_without_runtime(monkeypatch):
    monkeypatch.setattr(bridge, "_rt", None)
    assert bridge._worker_version() == "unknown"


def test_worker_version_reads_runtime_version(monkeypatch):
    fake_rt = SimpleNamespace(version=SimpleNamespace(VERSION="9.9.9"))
    monkeypatch.setattr(bridge, "_rt", fake_rt)
    assert bridge._worker_version() == "9.9.9"


def test_tuple_to_datum_wraps_typed_data_collections(monkeypatch):
    monkeypatch.setattr(
        bridge, "_Datum",
        lambda value, kind: SimpleNamespace(value=value, type=kind))

    string_datum = bridge._tuple_to_datum(
        ("collection_string", ["first", "second"]))
    bytes_datum = bridge._tuple_to_datum(
        ("collection_bytes", [b"first", b"second"]))

    assert string_datum.value.string == ["first", "second"]
    assert string_datum.value.bytes == []
    assert bytes_datum.value.bytes == [b"first", b"second"]
    assert bytes_datum.value.string == []


def test_invoke_native_forwards_retry_context(monkeypatch):
    captured = {}

    def run_invocation_sync(*args):
        captured["args"] = args
        return (True, True, None, [], None)

    native = SimpleNamespace(run_invocation_sync=run_invocation_sync)
    monkeypatch.setattr(bridge, "_ensure_native", lambda: native)

    result = bridge.invoke_native(
        "function-id", "invocation-id", [], {}, "trace-parent", "trace-state",
        {"retry_count": 2, "max_retry_count": 3,
         "exception": {"message": "previous attempt failed",
                       "stack_trace": "stack", "source": "host",
                       "type": "ExampleError"}})

    assert result == (True, None, [], None)
    assert captured["args"][6:8] == (2, 3)
    retry_exception = captured["args"][8]
    assert retry_exception.message == "previous attempt failed"
    assert retry_exception.stack_trace == "stack"
    assert retry_exception.source == "host"
    assert retry_exception.type == "ExampleError"
