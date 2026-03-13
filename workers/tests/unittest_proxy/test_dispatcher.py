import asyncio
import builtins
import logging
import threading
import types
import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock, ANY

import pytest

from proxy_worker.dispatcher import (
    Dispatcher,
    ContextEnabledTask,
    set_current_invocation_id,
    get_global_current_invocation_id,
    get_current_invocation_id,
    set_thread_invocation_id,
    get_thread_invocation_id,
    clear_thread_invocation_id,
)


_real_import = builtins.__import__


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
        # Import module to access cached constants
        import proxy_worker.dispatcher as dispatcher_module

        loop = Mock()
        dispatcher = Dispatcher(loop, "localhost", 5000, "worker",
                                "req", 5.0)

        mock_rpc_log.return_value = Mock()
        mock_streaming_message.return_value = Mock()

        levels = [
            (logging.CRITICAL, dispatcher_module._LOG_LEVEL_CRITICAL),
            (logging.ERROR, dispatcher_module._LOG_LEVEL_ERROR),
            (logging.WARNING, dispatcher_module._LOG_LEVEL_WARNING),
            (logging.INFO, dispatcher_module._LOG_LEVEL_INFO),
            (logging.DEBUG, dispatcher_module._LOG_LEVEL_DEBUG),
            (5, dispatcher_module._LOG_LEVEL_NONE),
        ]

        for level, expected in levels:
            record = Mock(levelno=level)
            record.name = "custom.logger"
            mock_is_system.return_value = level % 2 == 0  # alternate True/False
            dispatcher.on_logging(record, "Test message")

            # Determine expected category from cached constants
            if mock_is_system.return_value:
                expected_category = dispatcher_module._LOG_CATEGORY_SYSTEM
            else:
                expected_category = dispatcher_module._LOG_CATEGORY_USER

            # Verify RpcLog was initialized with correct mapped values
            # We use call_args to verify kwargs, ignoring any extra kwargs
            # like invocation_id if present
            args, kwargs = mock_rpc_log.call_args
            self.assertEqual(kwargs['level'], expected)
            self.assertEqual(kwargs['log_category'], expected_category)
            self.assertEqual(kwargs['message'], "Test message")
            self.assertEqual(kwargs['category'], "custom.logger")


def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
    mock_module = types.SimpleNamespace(__file__=f"{name}.py")
    mock_module.worker_init_request = AsyncMock(return_value="fake_response")
    mock_module.function_environment_reload_request = AsyncMock(
        return_value="mocked_env_reload_response")
    mock_module.version = AsyncMock(return_value="fake_response")
    mock_module.version.VERSION = AsyncMock(return_value="1.0.0")
    if name in ["azure_functions_runtime", "azure_functions_runtime_v1"]:
        return mock_module
    return _real_import(name, globals, locals, fromlist, level)


@patch("proxy_worker.dispatcher.DependencyManager.should_load_cx_dependencies",
       return_value=True)
@patch("proxy_worker.dispatcher.DependencyManager.prioritize_customer_dependencies")
@patch("proxy_worker.dispatcher.logger")
@patch("proxy_worker.dispatcher.os.path.exists",
       side_effect=lambda p: p.endswith("function_app.py"))
@patch("builtins.__import__", side_effect=fake_import)
@patch("proxy_worker.dispatcher.protos.StreamingMessage",
       return_value="mocked_streaming_response")
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_worker_init_v2_import(
        mock_eol, mock_streaming, mock_import, mock_exists,
        mock_logger, mock_prioritize,
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
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_worker_init_fallback_to_v1(
        mock_eol, mock_streaming, mock_import, mock_exists,
        mock_logger, mock_prioritize,
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
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_function_environment_reload_v2_import(
        mock_eol, mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize
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
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_function_environment_reload_fallback_to_v1(
        mock_eol, mock_streaming, mock_import, mock_exists, mock_logger, mock_prioritize
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
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_worker_init_starts_threadpool(mock_eol, mock_streaming,
                                             mock_import, *_mocks):
    runtime_module = _make_runtime_module(with_threadpool=True)

    def fake_import(name, *a, **k):
        if name == "azure_functions_runtime":
            return runtime_module
        return _real_import(name, *a, **k)

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
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_env_reload_starts_threadpool(mock_eol, mock_streaming,
                                            mock_import, *_mocks):
    runtime_module = _make_runtime_module(with_threadpool=True)

    def fake_import(name, *a, **k):
        if name == "azure_functions_runtime":
            return runtime_module
        return _real_import(name, *a, **k)

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
@patch("proxy_worker.dispatcher.check_python_eol")
@pytest.mark.asyncio
async def test_worker_init_missing_threadpool_apis(mock_eol,
                                                   mock_streaming, mock_import,
                                                   mock_exists, mock_logger, *_):
    runtime_module = _make_runtime_module(with_threadpool=False)

    def fake_import(name, *a, **k):
        if name == "azure_functions_runtime":
            return runtime_module
        return _real_import(name, *a, **k)

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


class TestInvocationTracking(unittest.TestCase):
    """Test suite for invocation ID tracking functionality"""

    def setUp(self):
        """Clear any existing invocation state before each test"""
        # Import the module-level variables properly
        import proxy_worker.dispatcher as dispatcher_module

        # Clear thread registry
        with dispatcher_module._registry_lock:
            dispatcher_module._thread_invocation_registry.clear()

        # Clear global invocation ID
        with dispatcher_module._current_invocation_lock:
            dispatcher_module._current_invocation_id = None

        # Clear library worker to ensure tests run with expected state
        dispatcher_module._library_worker = None

    def tearDown(self):
        """Clean up after each test"""
        # Import the module-level variables properly
        import proxy_worker.dispatcher as dispatcher_module

        # Clear thread registry
        with dispatcher_module._registry_lock:
            dispatcher_module._thread_invocation_registry.clear()

        # Clear global invocation ID
        with dispatcher_module._current_invocation_lock:
            dispatcher_module._current_invocation_id = None

        # Clear library worker
        dispatcher_module._library_worker = None

    def test_global_invocation_id_set_and_get(self):
        """Test setting and getting global current invocation ID"""
        test_id = "test-invocation-123"

        # Initially should be None
        self.assertIsNone(get_global_current_invocation_id())

        # Set and verify
        set_current_invocation_id(test_id)
        self.assertEqual(get_global_current_invocation_id(), test_id)

        # Test overwrite
        new_id = "new-invocation-456"
        set_current_invocation_id(new_id)
        self.assertEqual(get_global_current_invocation_id(), new_id)

    def test_thread_invocation_registry(self):
        """Test thread-specific invocation ID registry"""
        thread_id = 12345
        invocation_id = "thread-invocation-789"

        # Initially should be None
        self.assertIsNone(get_thread_invocation_id(thread_id))

        # Set and verify
        set_thread_invocation_id(thread_id, invocation_id)
        self.assertEqual(get_thread_invocation_id(thread_id), invocation_id)

        # Test clear
        clear_thread_invocation_id(thread_id)
        self.assertIsNone(get_thread_invocation_id(thread_id))

        # Test clear non-existent (should not raise)
        clear_thread_invocation_id(99999)

    def test_get_current_invocation_id_ignores_global_by_default(self):
        """Test that global invocation ID is ignored by default"""
        global_id = "global-123"
        thread_id = threading.get_ident()
        thread_id_value = "thread-456"

        # Set both global and thread-specific
        set_current_invocation_id(global_id)
        set_thread_invocation_id(thread_id, thread_id_value)

        # Thread should take priority (global is ignored)
        result = get_current_invocation_id()
        self.assertEqual(result, thread_id_value)

    def test_get_current_invocation_id_fallback_to_thread(self):
        """Test fallback to thread registry when global is None"""
        thread_id = threading.get_ident()
        thread_id_value = "thread-only-789"

        # Set only thread-specific
        set_thread_invocation_id(thread_id, thread_id_value)

        # Should fallback to thread registry
        result = get_current_invocation_id()
        self.assertEqual(result, thread_id_value)

    @patch('proxy_worker.dispatcher.asyncio._get_running_loop')
    @patch('proxy_worker.dispatcher.asyncio.current_task')
    def test_get_current_invocation_id_asyncio_task_context(
            self, mock_current_task, mock_get_loop):
        """Test getting invocation ID from asyncio task context"""
        # Setup mocks
        mock_loop = Mock()
        mock_get_loop.return_value = mock_loop

        mock_task = Mock(spec=ContextEnabledTask)
        mock_task.__azure_function_invocation_id__ = "task-invocation-999"
        mock_current_task.return_value = mock_task

        # Should get from task context when no global/thread IDs
        result = get_current_invocation_id()
        self.assertEqual(result, "task-invocation-999")

    @patch('proxy_worker.dispatcher.asyncio._get_running_loop')
    def test_get_current_invocation_id_no_running_loop(self, mock_get_loop):
        """Test behavior when no asyncio loop is running"""
        mock_get_loop.side_effect = RuntimeError("No running event loop")

        # Should handle RuntimeError gracefully and return None
        result = get_current_invocation_id()
        self.assertIsNone(result)

    def test_context_enabled_task_invocation_id_inheritance(self):
        """Test that ContextEnabledTask inherits invocation ID from parent task"""
        # Create a mock parent task with invocation ID
        parent_task = Mock(spec=ContextEnabledTask)
        parent_task.__azure_function_invocation_id__ = "parent-invocation-123"

        # Create real async coroutine
        async def dummy_coro():
            return "test"

        # Create mock loop
        mock_loop = Mock()

        with patch('asyncio.current_task', return_value=parent_task):
            # Create ContextEnabledTask
            task = ContextEnabledTask(dummy_coro(), mock_loop)

            # Should inherit parent's invocation ID
            self.assertEqual(
                getattr(task, ContextEnabledTask.AZURE_INVOCATION_ID),
                "parent-invocation-123"
            )

    def test_context_enabled_task_set_invocation_id(self):
        """Test setting invocation ID on ContextEnabledTask"""
        # Create real async coroutine
        async def dummy_coro():
            return "test"

        mock_loop = Mock()

        with patch('asyncio.current_task', return_value=None):
            task = ContextEnabledTask(dummy_coro(), mock_loop)

            # Set invocation ID
            test_id = "direct-set-456"
            task.set_azure_invocation_id(test_id)

            # Verify it was set
            self.assertEqual(
                getattr(task, ContextEnabledTask.AZURE_INVOCATION_ID),
                test_id
            )

    def test_thread_safety_concurrent_access(self):
        """Test thread safety of invocation ID operations"""
        import concurrent.futures
        import time

        results = []
        errors = []

        def worker_thread(thread_num):
            try:
                thread_id = threading.get_ident()
                invocation_id = f"concurrent-{thread_num}-{thread_id}"

                # Set thread-specific invocation ID
                set_thread_invocation_id(thread_id, invocation_id)

                # Small delay to increase chance of race conditions
                time.sleep(0.001)

                # Get and verify
                retrieved = get_thread_invocation_id(thread_id)
                results.append((thread_num, invocation_id, retrieved))

                # Clean up
                clear_thread_invocation_id(thread_id)

            except Exception as e:
                errors.append((thread_num, str(e)))

        # Run multiple threads concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(20)]
            concurrent.futures.wait(futures)

        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")

        # Verify all operations completed correctly
        self.assertEqual(len(results), 20)
        for thread_num, original, retrieved in results:
            self.assertEqual(original, retrieved,
                             f"Thread {thread_num}: {original} != {retrieved}")


class TestDispatcherInvocationHandling(unittest.TestCase):
    """Test dispatcher's handling of invocation requests with ID tracking"""

    def setUp(self):
        """Clear any existing invocation state before each test"""
        # Import the module-level variables properly
        import proxy_worker.dispatcher as dispatcher_module

        # Clear thread registry
        with dispatcher_module._registry_lock:
            dispatcher_module._thread_invocation_registry.clear()

        # Clear global invocation ID
        with dispatcher_module._current_invocation_lock:
            dispatcher_module._current_invocation_id = None

    def tearDown(self):
        """Clean up after each test"""
        # Import the module-level variables properly
        import proxy_worker.dispatcher as dispatcher_module

        # Clear thread registry
        with dispatcher_module._registry_lock:
            dispatcher_module._thread_invocation_registry.clear()

        # Clear global invocation ID
        with dispatcher_module._current_invocation_lock:
            dispatcher_module._current_invocation_id = None

    @patch("proxy_worker.dispatcher._library_worker")
    @patch("proxy_worker.dispatcher.protos.StreamingMessage")
    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.asyncio.current_task")
    @pytest.mark.asyncio
    async def test_invocation_request_sets_all_contexts(
            self, mock_current_task, mock_logger, mock_streaming,
            mock_library_worker):
        """Test that invocation request sets global, task, and thread contexts"""
        # Setup mocks
        mock_library_worker.invocation_request = AsyncMock(
            return_value="mocked_response")
        mock_streaming.return_value = "mocked_stream_response"

        mock_task = Mock(spec=ContextEnabledTask)
        mock_current_task.return_value = mock_task

        # Create dispatcher
        dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                                "worker123", "req789", 5.0)

        # Create request
        request = Mock()
        request.invocation_request.invocation_id = "test-invocation-123"
        request.invocation_request.function_id = "func123"

        # Call the handler
        result = await dispatcher._handle__invocation_request(request)

        # Verify global invocation ID was set
        self.assertEqual(get_global_current_invocation_id(),
                         "test-invocation-123")

        # Verify task invocation ID was set
        mock_task.set_azure_invocation_id.assert_called_once_with(
            "test-invocation-123")

        # Verify thread registry was updated
        current_thread_id = threading.get_ident()
        self.assertEqual(get_thread_invocation_id(current_thread_id),
                         "test-invocation-123")

        # Verify library worker was called
        mock_library_worker.invocation_request.assert_called_once()

        # Verify response
        self.assertEqual(result, "mocked_stream_response")

    @patch("proxy_worker.dispatcher._library_worker")
    @patch("proxy_worker.dispatcher.protos.StreamingMessage")
    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.asyncio.current_task")
    @pytest.mark.asyncio
    async def test_invocation_request_cleans_up_on_exception(
            self, mock_current_task, mock_logger, mock_streaming,
            mock_library_worker):
        """Test that thread registry is cleaned up when invocation fails"""
        # Setup mocks to raise exception
        mock_library_worker.invocation_request = AsyncMock(
            side_effect=Exception("Test exception")
        )

        mock_task = Mock(spec=ContextEnabledTask)
        mock_current_task.return_value = mock_task

        # Create dispatcher
        dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                                "worker123", "req789", 5.0)

        # Create request
        request = Mock()
        request.invocation_request.invocation_id = "test-invocation-456"
        request.invocation_request.function_id = "func123"

        current_thread_id = threading.get_ident()

        # Call should raise exception
        with self.assertRaises(Exception) as cm:
            await dispatcher._handle__invocation_request(request)

        self.assertEqual(str(cm.exception), "Test exception")

        # Verify thread registry was cleaned up
        self.assertIsNone(get_thread_invocation_id(current_thread_id))

        # Verify global invocation ID is still set (not cleared on exception)
        self.assertEqual(get_global_current_invocation_id(),
                         "test-invocation-456")

    @patch("proxy_worker.dispatcher._library_worker")
    @patch("proxy_worker.dispatcher.protos.StreamingMessage")
    @patch("proxy_worker.dispatcher.logger")
    @pytest.mark.asyncio
    async def test_invocation_request_handles_no_current_task(
            self, mock_logger, mock_streaming, mock_library_worker):
        """Test invocation request when no current asyncio task exists"""
        # Setup mocks
        mock_library_worker.invocation_request = AsyncMock(
            return_value="mocked_response")
        mock_streaming.return_value = "mocked_stream_response"

        # Create dispatcher
        dispatcher = Dispatcher(asyncio.get_event_loop(), "localhost", 7071,
                                "worker123", "req789", 5.0)

        # Create request
        request = Mock()
        request.invocation_request.invocation_id = "no-task-invocation-789"
        request.invocation_request.function_id = "func123"

        # Mock current_task to return None
        with patch("proxy_worker.dispatcher.asyncio.current_task",
                   return_value=None):
            result = await dispatcher._handle__invocation_request(request)

        # Should still set global and thread contexts
        self.assertEqual(get_global_current_invocation_id(),
                         "no-task-invocation-789")

        current_thread_id = threading.get_ident()
        self.assertEqual(get_thread_invocation_id(current_thread_id),
                         "no-task-invocation-789")

        # Verify response
        self.assertEqual(result, "mocked_stream_response")
