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
    def test_on_logging_levels_and_categories(self, mock_is_system, mock_rpc_log,
                                              mock_streaming_message):
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
    mock_module.function_environment_reload_request = AsyncMock(
        return_value="mocked_env_reload_response")
    mock_module.version = AsyncMock(return_value="fake_response")
    mock_module.version.VERSION = AsyncMock(return_value="1.0.0")
    if name in ["azure_functions_runtime", "azure_functions_runtime_v1"]:
        return mock_module
    return builtins.__import__(name, globals, locals, fromlist, level)


@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies",
       return_value=True)
@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists",
       side_effect=lambda p: p.endswith("function_app.py"))
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_streaming_response")
@pytest.mark.asyncio
async def test_worker_init_v2_import(
        mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize,
        mock_should_load
):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)
    request = MagicMock()
    request.worker_init_request.function_app_directory = "/home/site/wwwroot"

    result = await dispatcher._handle__worker_init_request(request)

    assert result == "mocked_streaming_response"
    mock_logger.debug.assert_any_call("azure_functions_runtime import succeeded: %s",
                                      ANY)


@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies",
       return_value=True)
@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: False)
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_streaming_response")
@pytest.mark.asyncio
async def test_worker_init_fallback_to_v1(
        mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize,
        mock_should_load
):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)
    request = MagicMock()
    request.worker_init_request.function_app_directory = "/home/site/wwwroot"

    result = await dispatcher._handle__worker_init_request(request)

    assert result == "mocked_streaming_response"
    mock_logger.debug.assert_any_call("azure_functions_runtime_v1 import succeeded: %s",
                                      ANY)


@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists",
       side_effect=lambda p: p.endswith("function_app.py"))
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_reload_response")
@pytest.mark.asyncio
async def test_function_environment_reload_v2_import(
        mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize
):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                            "worker123", "req789", 5.0)
    request = MagicMock()
    request.function_environment_reload_request.function_app_directory = \
        "/home/site/wwwroot"

    result = await dispatcher._handle__function_environment_reload_request(request)

    assert result == "mocked_reload_response"
    mock_logger.debug.assert_any_call("azure_functions_runtime import succeeded: %s",
                                      ANY)


@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: False)
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_reload_response")
@pytest.mark.asyncio
async def test_function_environment_reload_fallback_to_v1(
        mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize
):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)
    request = MagicMock()
    request.function_environment_reload_request.function_app_directory = "/some/path"

    result = await dispatcher._handle__function_environment_reload_request(request)

    assert result == "mocked_reload_response"
    mock_logger.debug.assert_any_call("azure_functions_runtime_v1 import succeeded: %s",
                                      ANY)


@patch("proxy_worker.dispatcher._library_worker",
       new=MagicMock(
           functions_metadata_request=AsyncMock(return_value="mocked_meta_resp")))
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_response")
@patch("proxy_worker.dispatcher.logger")
@pytest.mark.asyncio
async def test_handle_functions_metadata_request(mock_logger, mock_streaming):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)
    request = MagicMock()
    request.request_id = "req789"

    result = await dispatcher._handle__functions_metadata_request(request)

    assert result == "mocked_response"
    mock_logger.info.assert_called_with(
        'Received WorkerMetadataRequest, request ID %s, worker id: %s',
        "req789", "worker123"
    )


@patch("proxy_worker.dispatcher._library_worker",
       new=MagicMock(
           function_load_request=AsyncMock(return_value="mocked_load_response")))
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_stream_response")
@patch("proxy_worker.dispatcher.logger")
@pytest.mark.asyncio
async def test_handle_function_load_request(mock_logger, mock_streaming):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)

    request = MagicMock()
    request.function_load_request.function_id = "func123"
    request.function_load_request.metadata.name = "hello_function"
    request.request_id = "req789"

    result = await dispatcher._handle__function_load_request(request)

    assert result == "mocked_stream_response"
    mock_logger.info.assert_called_with(
        'Received WorkerLoadRequest, request ID %s, function_id: %s, function_name: %s,'
        ' worker_id: %s', "req789", "func123", "hello_function", "worker123"
    )


@patch("proxy_worker.dispatcher._library_worker",
       new=MagicMock(
           invocation_request=AsyncMock(return_value="mocked_invoc_response")))
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_streaming_response")
@patch("proxy_worker.dispatcher.logger")
@pytest.mark.asyncio
async def test_handle_invocation_request(mock_logger, mock_streaming):
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071, "worker123",
                            "req789", 5.0)

    request = MagicMock()
    request.invocation_request.invocation_id = "inv123"
    request.invocation_request.function_id = "func123"
    request.request_id = "req789"

    result = await dispatcher._handle__invocation_request(request)

    assert result == "mocked_streaming_response"
    mock_logger.info.assert_called_with(
        'Received FunctionInvocationRequest, request ID %s, function_id: %s, '
        'invocation_id: %s, worker_id: %s',
        "req789", "func123", "inv123", "worker123"
    )


def _make_runtime_module(with_threadpool=True):
    mod = types.SimpleNamespace(__file__="azure_functions_runtime.py")

    async def _async_ok(*_a, **_k):
        return "ok"

    mod.worker_init_request = _async_ok
    mod.function_environment_reload_request = _async_ok
    mod.version = types.SimpleNamespace(VERSION="1.2.3")
    if with_threadpool:
        state = {"started": 0, "stopped": 0}

        def start_threadpool_executor():
            state["started"] += 1

        def stop_threadpool_executor():
            state["stopped"] += 1

        def get_threadpool_executor():
            return object()

        mod.start_threadpool_executor = start_threadpool_executor
        mod.stop_threadpool_executor = stop_threadpool_executor
        mod.get_threadpool_executor = get_threadpool_executor
        mod._state = state
    return mod


@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies",
       return_value=False)
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: True)
@patch("builtins.__import__")
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_init_response")
@pytest.mark.asyncio
async def test_worker_init_starts_threadpool(mock_streaming, mock_import, *_mocks):
    runtime_module = _make_runtime_module(with_threadpool=True)

    def fake_import(name, *a, **k):
        if name == "azure_functions_runtime":
            return runtime_module
        return builtins.__import__(name, *a, **k)

    mock_import.side_effect = fake_import
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                            "workerABC", "reqXYZ", 5.0)
    req = MagicMock()
    req.worker_init_request.function_app_directory = "/site/wwwroot"
    await dispatcher._handle__worker_init_request(req)
    assert runtime_module._state["started"] == 1
    # _sync_call_tp should not exist after refactor
    assert not hasattr(dispatcher, "_sync_call_tp")


@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: True)
@patch("builtins.__import__")
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_reload_response")
@pytest.mark.asyncio
async def test_env_reload_starts_threadpool(mock_streaming, mock_import, *_mocks):
    runtime_module = _make_runtime_module(with_threadpool=True)

    def fake_import(name, *a, **k):
        if name == "azure_functions_runtime":
            return runtime_module
        return builtins.__import__(name, *a, **k)

    mock_import.side_effect = fake_import
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                            "workerABC", "reqXYZ", 5.0)
    # simulate worker init first
    init_req = MagicMock()
    init_req.worker_init_request.function_app_directory = "/site/wwwroot"
    await dispatcher._handle__worker_init_request(init_req)
    reload_req = MagicMock()
    reload_req.function_environment_reload_request.function_app_directory = (
        "/site/wwwroot")
    await dispatcher._handle__function_environment_reload_request(reload_req)
    # start called twice: once on init, once on reload
    assert runtime_module._state["started"] == 2
    assert not hasattr(dispatcher, "_sync_call_tp")


@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies",
       return_value=False)
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists", side_effect=lambda p: True)
@patch("builtins.__import__")
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_init_response")
@pytest.mark.asyncio
async def test_worker_init_missing_threadpool_apis(mock_streaming, mock_import,
                                                   mock_exists, mock_logger, *_):
    runtime_module = _make_runtime_module(with_threadpool=False)

    def fake_import(name, *a, **k):
        if name == "azure_functions_runtime":
            return runtime_module
        return builtins.__import__(name, *a, **k)

    mock_import.side_effect = fake_import
    dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                            "workerDEF", "req123", 5.0)
    req = MagicMock()
    req.worker_init_request.function_app_directory = "/site/wwwroot"
    await dispatcher._handle__worker_init_request(req)
    # Ensure we logged the debug message about missing APIs
    mock_logger.debug.assert_any_call(
        "Threadpool executor APIs not present in runtime; skipping start.")
    assert not hasattr(dispatcher, "_sync_call_tp")
