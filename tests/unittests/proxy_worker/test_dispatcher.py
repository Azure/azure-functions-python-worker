import asyncio
import builtins
import logging
import types
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, ANY

import pytest

from proxy_worker.dispatcher import Dispatcher


class TestDispatcher(unittest.TestCase):

    @patch("proxy_worker.dispatcher.queue.Queue")
    @patch("proxy_worker.dispatcher.threading.Thread")
    def test_dispatcher_initialization(self, mock_thread, mock_queue):
        # Arrange
        mock_loop = Mock()
        mock_future = Mock()
        mock_loop.create_future.return_value = mock_future

        # Act
        dispatcher = Dispatcher(
            loop=mock_loop,
            host="127.0.0.1",
            port=7070,
            worker_id="worker123",
            request_id="req456",
            grpc_connect_timeout=5.0,
            grpc_max_msg_len=1024
        )

        # Assert
        self.assertEqual(dispatcher._host, "127.0.0.1")
        self.assertEqual(dispatcher._port, 7070)
        self.assertEqual(dispatcher._worker_id, "worker123")
        self.assertEqual(dispatcher._request_id, "req456")
        self.assertEqual(dispatcher._grpc_connect_timeout, 5.0)
        self.assertEqual(dispatcher._grpc_max_msg_len, 1024)
        self.assertEqual(dispatcher._grpc_connected_fut, mock_future)
        mock_queue.assert_called_once()
        mock_thread.assert_called_once()

    @patch("proxy_worker.dispatcher.protos.StreamingMessage")
    @patch("proxy_worker.dispatcher.protos.RpcLog")
    @patch("proxy_worker.dispatcher.is_system_log_category")
    def test_on_logging_levels_and_categories(self, mock_is_system, mock_rpc_log, mock_streaming_message):
        loop = Mock()
        dispatcher = Dispatcher(loop, "localhost", 5000, "worker",
                                "req", 5.0)

        mock_rpc_log.return_value = Mock()
        mock_streaming_message.return_value = Mock()

        levels = [
            (logging.CRITICAL, mock_rpc_log.Critical),
            (logging.ERROR, mock_rpc_log.Error),
            (logging.WARNING, mock_rpc_log.Warning),
            (logging.INFO, mock_rpc_log.Information),
            (logging.DEBUG, mock_rpc_log.Debug),
            (5, getattr(mock_rpc_log, 'None')),
        ]

        for level, expected in levels:
            record = Mock(levelno=level, name="custom.logger")
            mock_is_system.return_value = level % 2 == 0  # alternate True/False
            dispatcher.on_logging(record, "Test message")

            if mock_is_system.return_value:
                mock_rpc_log.RpcLogCategory.Value.assert_called_with("System")
            else:
                mock_rpc_log.RpcLogCategory.Value.assert_called_with("User")


def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
    mock_module = types.SimpleNamespace(__file__=f"{name}.py")
    mock_module.worker_init_request = AsyncMock(return_value="fake_response")
    mock_module.function_environment_reload_request = AsyncMock(return_value="mocked_env_reload_response")
    if name in ["azure_functions_worker_v2", "azure_functions_worker_v1"]:
        return mock_module
    return builtins.__import__(name, globals, locals, fromlist, level)



@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies", return_value=True)
@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: p.endswith("function_app.py"))
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage", return_value="mocked_streaming_response")
@pytest.mark.asyncio
async def test_worker_init_v2_import(
    mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize, mock_should_load
):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)
    request = MagicMock()
    request.worker_init_request.function_app_directory = "/home/site/wwwroot"

    result = await dispatcher._handle__worker_init_request(request)

    assert result == "mocked_streaming_response"
    mock_logger.debug.assert_any_call("V2 worker import succeeded: %s", ANY)


@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies", return_value=True)
@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: False)
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage", return_value="mocked_streaming_response")
@pytest.mark.asyncio
async def test_worker_init_fallback_to_v1(
    mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize, mock_should_load
):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)
    request = MagicMock()
    request.worker_init_request.function_app_directory = "/home/site/wwwroot"

    result = await dispatcher._handle__worker_init_request(request)

    assert result == "mocked_streaming_response"
    mock_logger.debug.assert_any_call("V1 worker import succeeded: %s", ANY)

@patch("proxy_worker.dispatcher.DependencyManager.reload_customer_libraries")
@patch("proxy_worker.dispatcher.protos.StreamingMessage", return_value="mocked_streaming_message")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: p.endswith("function_app.py"))
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.logger")
@pytest.mark.asyncio
async def test_function_environment_reload_v2_success(
    mock_logger, mock_import, mock_exists, mock_streaming, mock_reload_libs
):
    dispatcher = Dispatcher(
        loop=MagicMock(),
        host="localhost",
        port=7071,
        worker_id="worker-test",
        request_id="req-abc",
        grpc_connect_timeout=5.0,
    )

    request = MagicMock()
    request.function_environment_reload_request.function_app_directory = "/home/site/wwwroot"

    result = await dispatcher._handle__function_environment_reload_request(request)

    assert result == "mocked_streaming_message"
    mock_logger.debug.assert_any_call("V2 worker import succeeded: %s", ANY)

@patch("proxy_worker.dispatcher.DependencyManager.reload_customer_libraries")
@patch("proxy_worker.dispatcher.protos.StreamingMessage", return_value="mocked_streaming_message")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: False)
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.logger")
@pytest.mark.asyncio
async def test_function_environment_reload_v1_success(
    mock_logger, mock_import, mock_exists, mock_streaming, mock_reload_libs
):
    dispatcher = Dispatcher(
        loop=MagicMock(),
        host="localhost",
        port=7071,
        worker_id="worker-test",
        request_id="req-abc",
        grpc_connect_timeout=5.0,
    )

    request = MagicMock()
    request.function_environment_reload_request.function_app_directory = "/home/site/wwwroot"

    result = await dispatcher._handle__function_environment_reload_request(request)

    assert result == "mocked_streaming_message"
    mock_logger.debug.assert_any_call("V1 worker import succeeded: %s", ANY)

