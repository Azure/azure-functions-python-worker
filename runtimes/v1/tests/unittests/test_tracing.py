# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import unittest
import traceback
from azure_functions_runtime_v1.utils.tracing import (extend_exception_message,
                                                      marshall_exception_trace,
                                                      serialize_exception,
                                                      serialize_exception_as_str)


class MockProtos:
    class RpcException:
        def __init__(self, message, stack_trace):
            self.message = message
            self.stack_trace = stack_trace


class TestExceptionUtils(unittest.TestCase):

    def test_extend_exception_message_basic(self):
        exc = ValueError("Original message")
        new_msg = "Extra info"
        new_exc = extend_exception_message(exc, new_msg)
        self.assertIsInstance(new_exc, ValueError)
        self.assertIn("Original message", str(new_exc))
        self.assertIn("Extra info", str(new_exc))
        self.assertTrue(str(new_exc).endswith(new_msg))

    def test_extend_exception_message_no_dot(self):
        exc = ValueError("Message without dot")
        new_exc = extend_exception_message(exc, "added")
        self.assertEqual(str(new_exc), "Message without dot. added")

    def test_marshall_exception_trace_basic(self):
        try:
            raise ValueError("Test")
        except ValueError as exc:
            trace = marshall_exception_trace(exc)
            self.assertIn("ValueError: Test", trace)
            self.assertIn("raise ValueError", trace)

    def test_marshall_exception_trace_module_not_found(self):
        try:
            import non_existent_module  # noqa: F401
        except ModuleNotFoundError as exc:
            trace = marshall_exception_trace(exc)
            self.assertIn("ModuleNotFoundError", trace)
            self.assertNotIn("<frozen importlib._bootstrap>", trace)

    def test_marshall_exception_trace_chained_exceptions(self):
        try:
            try:
                raise ValueError("Inner error")
            except ValueError as inner:
                raise RuntimeError("Outer error") from inner
        except RuntimeError as exc:
            trace = marshall_exception_trace(exc)
            # Outer exception must appear
            self.assertIn("RuntimeError: Outer error", trace)
            # Inner exception must also appear
            self.assertIn("ValueError: Inner error", trace)
            # Ensure 'The above exception was the direct cause' appears
            self.assertIn("The above exception was the direct cause", trace)

    def test_serialize_exception_returns_rpc_exception(self):
        try:
            raise ValueError("Error for proto")
        except ValueError as exc:
            result = serialize_exception(exc, MockProtos)
            self.assertIsInstance(result, MockProtos.RpcException)
            self.assertIn("ValueError", result.message)
            self.assertIn("Error for proto", result.message)
            self.assertIn("raise ValueError", result.stack_trace)

    def test_serialize_exception_as_str_basic(self):
        try:
            raise RuntimeError("Runtime issue")
        except RuntimeError as exc:
            result = serialize_exception_as_str(exc)
            self.assertIn("RuntimeError: Runtime issue", result)
            self.assertIn("Stack Trace:", result)
            self.assertIn("raise RuntimeError", result)

    def test_serialize_exception_with_unserializable_exception(self):
        class BadExc(Exception):
            def __str__(self):
                raise ValueError("Cannot stringify")

        exc = BadExc()
        result_str = serialize_exception_as_str(exc)
        self.assertIn("Could not serialize original exception message", result_str)

        result_proto = serialize_exception(exc, MockProtos)
        self.assertIn("Could not serialize original exception message",
                      result_proto.message)

    def test_marshall_exception_trace_sub_exception(self):
        # Patch traceback.format_exception to raise inside marshall_exception_trace
        original_format_exception = traceback.format_exception

        def bad_format(*args, **kwargs):
            raise RuntimeError("fail inside traceback")
        traceback.format_exception = bad_format
        try:
            exc = ValueError("test")
            result = marshall_exception_trace(exc)
            self.assertIn("Could not extract traceback", result)
            self.assertIn("RuntimeError", result)
        finally:
            traceback.format_exception = original_format_exception
