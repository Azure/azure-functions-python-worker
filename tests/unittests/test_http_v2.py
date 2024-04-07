import asyncio
import socket
import sys
import unittest
from unittest.mock import MagicMock, patch

from azure_functions_worker.http_v2 import http_coordinator, \
    AsyncContextReference, SingletonMeta, get_unused_tcp_port


class MockHttpRequest:
    pass


class MockHttpResponse:
    pass


@unittest.skipIf(sys.version_info <= (3, 7), "Skipping tests if <= Python 3.7")
class TestHttpCoordinator(unittest.TestCase):
    def setUp(self):
        self.invoc_id = "test_invocation"
        self.http_request = MockHttpRequest()
        self.http_response = MockHttpResponse()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        http_coordinator._context_references.clear()
        self.loop.close()

    def test_set_http_request_new_invocation(self):
        # Test setting a new HTTP request
        http_coordinator.set_http_request(self.invoc_id, self.http_request)
        context_ref = http_coordinator._context_references.get(self.invoc_id)
        self.assertIsNotNone(context_ref)
        self.assertEqual(context_ref.http_request, self.http_request)

    def test_set_http_request_existing_invocation(self):
        # Test updating an existing HTTP request
        new_http_request = MagicMock()
        http_coordinator.set_http_request(self.invoc_id, new_http_request)
        context_ref = http_coordinator._context_references.get(self.invoc_id)
        self.assertIsNotNone(context_ref)
        self.assertEqual(context_ref.http_request, new_http_request)

    def test_set_http_response_context_ref_null(self):
        with self.assertRaises(Exception) as cm:
            http_coordinator.set_http_response(self.invoc_id,
                                               self.http_response)
        self.assertEqual(cm.exception.args[0],
                         "No context reference found for invocation "
                         f"{self.invoc_id}")

    def test_set_http_response(self):
        http_coordinator.set_http_request(self.invoc_id, self.http_request)
        http_coordinator.set_http_response(self.invoc_id, self.http_response)
        context_ref = http_coordinator._context_references[self.invoc_id]
        self.assertEqual(context_ref.http_response, self.http_response)

    def test_get_http_request_async_existing_invocation(self):
        # Test retrieving an existing HTTP request
        http_coordinator.set_http_request(self.invoc_id,
                                          self.http_request)
        retrieved_request = self.loop.run_until_complete(
            http_coordinator.get_http_request_async(self.invoc_id))
        self.assertEqual(retrieved_request, self.http_request)

    def test_get_http_request_async_wait_forever(self):
        # Test handling error when invoc_id is not found
        invalid_invoc_id = "invalid_invocation"

        with self.assertRaises(asyncio.TimeoutError):
            self.loop.run_until_complete(
                asyncio.wait_for(
                    http_coordinator.get_http_request_async(
                        invalid_invoc_id),
                    timeout=1
                )
            )

    def test_await_http_response_async_valid_invocation(self):
        invoc_id = "valid_invocation"
        expected_response = self.http_response

        context_ref = AsyncContextReference(http_response=expected_response)

        # Add the mock context reference to the coordinator
        http_coordinator._context_references[invoc_id] = context_ref

        http_coordinator.set_http_response(invoc_id, expected_response)

        # Call the method and verify the returned response
        response = self.loop.run_until_complete(
            http_coordinator.await_http_response_async(invoc_id))
        self.assertEqual(response, expected_response)
        self.assertTrue(
            http_coordinator._context_references.get(
                invoc_id).http_response is None)

    def test_await_http_response_async_invalid_invocation(self):
        # Test handling error when invoc_id is not found
        invalid_invoc_id = "invalid_invocation"
        with self.assertRaises(Exception) as context:
            self.loop.run_until_complete(
                http_coordinator.await_http_response_async(invalid_invoc_id))
        self.assertEqual(str(context.exception),
                         f"No context reference found for invocation "
                         f"{invalid_invoc_id}")

    def test_await_http_response_async_response_not_set(self):
        invoc_id = "invocation_with_no_response"
        # Set up a mock context reference without setting the response
        context_ref = AsyncContextReference()

        # Add the mock context reference to the coordinator
        http_coordinator._context_references[invoc_id] = context_ref

        http_coordinator.set_http_response(invoc_id, None)
        # Call the method and verify that it raises an exception
        with self.assertRaises(Exception) as context:
            self.loop.run_until_complete(
                http_coordinator.await_http_response_async(invoc_id))
        self.assertEqual(str(context.exception),
                         f"No http response found for invocation {invoc_id}")


@unittest.skipIf(sys.version_info <= (3, 7), "Skipping tests if <= Python 3.7")
class TestAsyncContextReference(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_init(self):
        ref = AsyncContextReference()
        self.assertIsInstance(ref, AsyncContextReference)
        self.assertTrue(ref.is_async)

    def test_http_request_property(self):
        ref = AsyncContextReference()
        ref.http_request = object()
        self.assertIsNotNone(ref.http_request)

    def test_http_response_property(self):
        ref = AsyncContextReference()
        ref.http_response = object()
        self.assertIsNotNone(ref.http_response)

    def test_function_property(self):
        ref = AsyncContextReference()
        ref.function = object()
        self.assertIsNotNone(ref.function)

    def test_fi_context_property(self):
        ref = AsyncContextReference()
        ref.fi_context = object()
        self.assertIsNotNone(ref.fi_context)

    def test_http_trigger_param_name_property(self):
        ref = AsyncContextReference()
        ref.http_trigger_param_name = object()
        self.assertIsNotNone(ref.http_trigger_param_name)

    def test_args_property(self):
        ref = AsyncContextReference()
        ref.args = object()
        self.assertIsNotNone(ref.args)

    def test_http_request_available_event_property(self):
        ref = AsyncContextReference()
        self.assertIsNotNone(ref.http_request_available_event)

    def test_http_response_available_event_property(self):
        ref = AsyncContextReference()
        self.assertIsNotNone(ref.http_response_available_event)

    def test_full_args(self):
        ref = AsyncContextReference(http_request=object(),
                                    http_response=object(),
                                    function=object(),
                                    fi_context=object(),
                                    args=object())
        self.assertIsNotNone(ref.http_request)
        self.assertIsNotNone(ref.http_response)
        self.assertIsNotNone(ref.function)
        self.assertIsNotNone(ref.fi_context)
        self.assertIsNotNone(ref.args)


class TestSingletonMeta(unittest.TestCase):

    def test_singleton_instance(self):
        class TestClass(metaclass=SingletonMeta):
            pass

        obj1 = TestClass()
        obj2 = TestClass()

        self.assertIs(obj1, obj2)

    def test_singleton_with_arguments(self):
        class TestClass(metaclass=SingletonMeta):
            def __init__(self, arg):
                self.arg = arg

        obj1 = TestClass(1)
        obj2 = TestClass(2)

        self.assertEqual(obj1.arg, 1)
        self.assertEqual(obj2.arg,
                         1)  # Should still refer to the same instance

    def test_singleton_with_kwargs(self):
        class TestClass(metaclass=SingletonMeta):
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        obj1 = TestClass(a=1)
        obj2 = TestClass(b=2)

        self.assertEqual(obj1.kwargs, {'a': 1})
        self.assertEqual(obj2.kwargs,
                         {'a': 1})  # Should still refer to the same instance


class TestGetUnusedTCPPort(unittest.TestCase):

    @patch('socket.socket')
    def test_get_unused_tcp_port(self, mock_socket):
        # Mock the socket object and its methods
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.getsockname.return_value = ('localhost', 12345)

        # Call the function
        port = get_unused_tcp_port()

        # Assert that socket.socket was called with the correct arguments
        mock_socket.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)

        # Assert that bind and close methods were called on the socket instance
        mock_socket_instance.bind.assert_called_once_with(('', 0))
        mock_socket_instance.close.assert_called_once()

        # Assert that the returned port matches the expected value
        self.assertEqual(port, 12345)
