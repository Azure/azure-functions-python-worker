# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from concurrent.futures import ThreadPoolExecutor
import threading
from types import SimpleNamespace

from azure_functions_runtime import native_invocation


def test_prepare_context_preserves_retry_context():
    function_info = SimpleNamespace(
        name="retry_function",
        directory="/functions/retry_function",
        requires_context=True,
        output_types={})
    args = {}
    retry_exception = SimpleNamespace(message="previous attempt failed")

    context = native_invocation._prepare_context(
        function_info, "invocation-id", args,
        retry_count=2, max_retry_count=3,
        retry_exception=retry_exception)

    assert args["context"] is context
    assert context.retry_context.retry_count == 2
    assert context.retry_context.max_retry_count == 3
    assert context.retry_context.rpc_exception is retry_exception


def test_run_invocation_sync_honors_runtime_threadpool_limit(monkeypatch):
    condition = threading.Condition()
    release = threading.Event()
    active = 0
    max_active = 0

    def function():
        nonlocal active, max_active
        with condition:
            active += 1
            max_active = max(max_active, active)
            condition.notify_all()
        release.wait(timeout=2)
        with condition:
            active -= 1

    function_info = SimpleNamespace(
        is_async=False,
        func=function,
        has_return=False,
        return_type=None,
    )
    monkeypatch.setattr(
        native_invocation, "_functions",
        SimpleNamespace(get_function=lambda function_id: function_info))
    monkeypatch.setattr(native_invocation, "_decode_inputs", lambda *args: {})
    monkeypatch.setattr(
        native_invocation, "_prepare_context",
        lambda *args: SimpleNamespace(
            thread_local_storage=SimpleNamespace()))
    monkeypatch.setattr(native_invocation, "_collect_output", lambda *args: [])

    runtime_executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(
        native_invocation, "get_threadpool_executor",
        lambda: runtime_executor)
    try:
        with ThreadPoolExecutor(max_workers=3) as callers:
            futures = [
                callers.submit(
                    native_invocation.run_invocation_sync,
                    f"invocation-{index}", "function-id", [], {})
                for index in range(3)
            ]
            with condition:
                condition.wait_for(lambda: active == 3, timeout=0.2)
            release.set()
            results = [future.result(timeout=2) for future in futures]
    finally:
        release.set()
        runtime_executor.shutdown(wait=True)

    assert max_active == 1
    assert all(result == (True, True, None, [], None, None)
               for result in results)


def test_run_invocation_sync_returns_customer_traceback(monkeypatch):
    def nested_helper():
        raise ValueError("bad input")

    function_info = SimpleNamespace(
        is_async=False,
        func=nested_helper,
        has_return=False,
        return_type=None,
    )
    monkeypatch.setattr(
        native_invocation, "_functions",
        SimpleNamespace(get_function=lambda function_id: function_info))
    monkeypatch.setattr(native_invocation, "_decode_inputs", lambda *args: {})
    monkeypatch.setattr(
        native_invocation, "_prepare_context",
        lambda *args: SimpleNamespace(
            thread_local_storage=SimpleNamespace()))

    runtime_executor = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(
        native_invocation, "get_threadpool_executor",
        lambda: runtime_executor)
    try:
        handled, ok, _, _, message, stack_trace = \
            native_invocation.run_invocation_sync(
                "invocation-id", "function-id", [], {})
    finally:
        runtime_executor.shutdown(wait=True)

    assert handled
    assert not ok
    assert message == "ValueError('bad input')"
    assert "nested_helper" in stack_trace
    assert "test_native_invocation.py" in stack_trace
