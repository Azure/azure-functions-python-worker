# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import collections as col
import contextvars
import os
import sys
import unittest
from typing import Optional, Tuple
from unittest.mock import patch

from azure_functions_worker import protos
from azure_functions_worker.constants import (PYTHON_THREADPOOL_THREAD_COUNT,
                                              PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT,
                                              PYTHON_THREADPOOL_THREAD_COUNT_MAX_37,
                                              PYTHON_THREADPOOL_THREAD_COUNT_MIN,
                                              PYTHON_ENABLE_INIT_INDEXING,
                                              METADATA_PROPERTIES_WORKER_INDEXED,
                                              PYTHON_ENABLE_DEBUG_LOGGING)
from azure_functions_worker.dispatcher import Dispatcher, ContextEnabledTask
from azure_functions_worker.version import VERSION
from tests.utils import testutils
from tests.utils.testutils import UNIT_TESTS_ROOT

SysVersionInfo = col.namedtuple("VersionInfo", ["major", "minor", "micro",
                                                "releaselevel", "serial"])
DISPATCHER_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / 'dispatcher_functions'
DISPATCHER_STEIN_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / \
    'dispatcher_functions' / \
    'dispatcher_functions_stein'
DISPATCHER_HTTP_V2_FASTAPI_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / \
    'dispatcher_functions' / \
    'http_v2' / \
    'fastapi'
FUNCTION_APP_DIRECTORY = UNIT_TESTS_ROOT / 'dispatcher_functions' / \
    'dispatcher_functions_stein'


class TestThreadPoolSettingsPython37(testutils.AsyncTestCase):
    """Base test class for testing thread pool settings for sync threadpool
    worker count. This class specifically sets sys.version_info to return as
    Python 3.7 and extended classes change this value and other platform
    specific values to test the behavior across the different python versions.

    Ref:
    NEW_TYPING = sys.version_info[:3] >= (3, 7, 0)  # PEP 560
    """

    def setUp(self, version=SysVersionInfo(3, 7, 0, 'final', 0)):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_FUNCTIONS_DIR)
        self._default_workers: Optional[
            int] = PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT
        self._over_max_workers: int = 10000
        self._allowed_max_workers: int = PYTHON_THREADPOOL_THREAD_COUNT_MAX_37
        self._pre_env = dict(os.environ)
        self.mock_version_info = patch(
            'azure_functions_worker.dispatcher.sys.version_info',
            version)
        self.mock_version_info.start()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_dispatcher_initialize_worker(self):
        """Test if the dispatcher can be initialized worker successfully
        """
        async with self._ctrl as host:
            r = await host.init_worker('3.0.12345')
            self.assertIsInstance(r.response, protos.WorkerInitResponse)
            self.assertIsInstance(r.response.worker_metadata,
                                  protos.WorkerMetadata)
            self.assertEqual(r.response.worker_metadata.runtime_name,
                             "python")
            self.assertEqual(r.response.worker_metadata.worker_version,
                             VERSION)

    async def test_dispatcher_environment_reload(self):
        """Test function environment reload response
        """
        async with self._ctrl as host:
            # Reload environment variable on specialization
            r = await host.reload_environment(environment={})
            self.assertIsInstance(r.response,
                                  protos.FunctionEnvironmentReloadResponse)
            self.assertIsInstance(r.response.worker_metadata,
                                  protos.WorkerMetadata)
            self.assertEqual(r.response.worker_metadata.runtime_name,
                             "python")
            self.assertEqual(r.response.worker_metadata.worker_version,
                             VERSION)

    async def test_dispatcher_initialize_worker_logging(self):
        """Test if the dispatcher's log can be flushed out during worker
        initialization
        """
        async with self._ctrl as host:
            r = await host.init_worker('3.0.12345')
            self.assertEqual(
                len([log for log in r.logs if log.message.startswith(
                    'Received WorkerInitRequest'
                )]),
                1
            )

    async def test_dispatcher_initialize_worker_settings_logs(self):
        """Test if the dispatcher's log can be flushed out during worker
        initialization
        """
        async with self._ctrl as host:
            r = await host.init_worker('3.0.12345')
            self.assertTrue('PYTHON_ENABLE_WORKER_EXTENSIONS: '
                            in log for log in r.logs)

    async def test_dispatcher_environment_reload_logging(self):
        """Test if the sync threadpool will pick up app setting in placeholder
        mode (Linux Consumption)
        """
        async with self._ctrl as host:
            await host.init_worker()
            await self._check_if_function_is_ok(host)

            # Reload environment variable on specialization
            r = await host.reload_environment(environment={})
            self.assertEqual(
                len([log for log in r.logs if log.message.startswith(
                    'Received FunctionEnvironmentReloadRequest'
                )]),
                1
            )

    async def test_dispatcher_environment_reload_settings_logs(self):
        """Test if the sync threadpool will pick up app setting in placeholder
        mode (Linux Consumption)
        """
        async with self._ctrl as host:
            await host.init_worker()
            await self._check_if_function_is_ok(host)

            # Reload environment variable on specialization
            r = await host.reload_environment(environment={})
            self.assertTrue('PYTHON_ENABLE_WORKER_EXTENSIONS: '
                            in log for log in r.logs)

    async def test_dispatcher_send_worker_request(self):
        """Test if the worker status response will be sent correctly when
        a worker status request is received
        """
        async with self._ctrl as host:
            r = await host.get_worker_status()
            self.assertIsInstance(r.response, protos.WorkerStatusResponse)

    async def test_dispatcher_sync_threadpool_default_worker(self):
        """Test if the sync threadpool has maximum worker count set the
        correct default value
        """
        async with self._ctrl as host:
            await host.init_worker()
            await self._check_if_function_is_ok(host)
            await self._assert_workers_threadpool(self._ctrl, host,
                                                  self._default_workers)

    async def test_dispatcher_sync_threadpool_set_worker(self):
        """Test if the sync threadpool maximum worker can be set
        """
        # Configure thread pool max worker
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT:
                           f'{self._allowed_max_workers}'})
        async with self._ctrl as host:
            await host.init_worker()
            await self._check_if_function_is_ok(host)
            await self._assert_workers_threadpool(self._ctrl, host,
                                                  self._allowed_max_workers)

    async def test_dispatcher_sync_threadpool_invalid_worker_count(self):
        """Test when sync threadpool maximum worker is set to an invalid value,
        the host should fallback to default value
        """
        # The @patch decorator does not work as expected and will suppress
        # any assertion failures in the async test cases.
        # Thus we're moving the patch() method to use the with syntax

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            # Configure thread pool max worker to an invalid value
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: 'invalid'})

            async with self._ctrl as host:
                await host.init_worker()
                await self._check_if_function_is_ok(host)
                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._default_workers)
            mock_logger.warning.assert_any_call(
                '%s must be an integer', PYTHON_THREADPOOL_THREAD_COUNT)

    async def test_dispatcher_sync_threadpool_below_min_setting(self):
        """Test if the sync threadpool will pick up default value when the
        setting is below minimum
        """
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            # Configure thread pool max worker to an invalid value
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '0'})
            async with self._ctrl as host:
                await host.init_worker()
                await self._check_if_function_is_ok(host)
                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._default_workers)
            mock_logger.warning.assert_any_call(
                '%s must be set to a value between %s and sys.maxint. '
                'Reverting to default value for max_workers',
                PYTHON_THREADPOOL_THREAD_COUNT,
                PYTHON_THREADPOOL_THREAD_COUNT_MIN)

    async def test_dispatcher_sync_threadpool_exceed_max_setting(self):
        """Test if the sync threadpool will pick up default max value when the
        setting is above maximum
        """
        with patch('azure_functions_worker.dispatcher.logger'):
            # Configure thread pool max worker to an invalid value
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT:
                               f'{self._over_max_workers}'})
            async with self._ctrl as host:
                await host.init_worker('4.15.1')
                await self._check_if_function_is_ok(host)

                # Ensure the dispatcher sync threadpool should fallback to max
                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._allowed_max_workers)

    async def test_dispatcher_sync_threadpool_in_placeholder(self):
        """Test if the sync threadpool will pick up app setting in placeholder
        mode (Linux Consumption)
        """
        async with self._ctrl as host:
            await host.init_worker()
            await self._check_if_function_is_ok(host)

            # Reload environment variable on specialization
            await host.reload_environment(environment={
                PYTHON_THREADPOOL_THREAD_COUNT: f'{self._allowed_max_workers}'
            })
            await self._assert_workers_threadpool(self._ctrl, host,
                                                  self._allowed_max_workers)

    async def test_dispatcher_sync_threadpool_in_placeholder_invalid(self):
        """Test if the sync threadpool will use the default setting when the
        app setting is invalid
        """
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with self._ctrl as host:
                await host.init_worker()
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: 'invalid'
                })
                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._default_workers)

                # Check warning message
                mock_logger.warning.assert_any_call(
                    '%s must be an integer', PYTHON_THREADPOOL_THREAD_COUNT)

    async def test_dispatcher_sync_threadpool_in_placeholder_above_max(self):
        """Test if the sync threadpool will use the default max setting when
        the app setting is above maximum.

        Note: This is designed for Linux Consumption.
        """
        with patch('azure_functions_worker.dispatcher.logger'):
            async with self._ctrl as host:
                await host.init_worker()
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: f'{self._over_max_workers}'
                })
                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._allowed_max_workers)

    async def test_dispatcher_sync_threadpool_in_placeholder_below_min(self):
        """Test if the sync threadpool will use the default setting when the
        app setting is below minimum
        """
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with self._ctrl as host:
                await host.init_worker()
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '0'
                })

                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._default_workers)

                mock_logger.warning.assert_any_call(
                    '%s must be set to a value between %s and sys.maxint. '
                    'Reverting to default value for max_workers',
                    PYTHON_THREADPOOL_THREAD_COUNT,
                    PYTHON_THREADPOOL_THREAD_COUNT_MIN)

    async def test_sync_invocation_request_log(self):
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with self._ctrl as host:
                await host.init_worker()
                request_id: str = self._ctrl._worker._request_id
                func_id, invoke_id, func_name = (
                    await self._check_if_function_is_ok(host)
                )

                logs, _ = mock_logger.info.call_args
                self.assertRegex(logs[0],
                                 'Received FunctionInvocationRequest, '
                                 f'request ID: {request_id}, '
                                 f'function ID: {func_id}, '
                                 f'function name: {func_name}, '
                                 f'invocation ID: {invoke_id}, '
                                 'function type: sync, '
                                 r'timestamp \(UTC\): '
                                 r'(\d{4}-\d{2}-\d{2} '
                                 r'\d{2}:\d{2}:\d{2}.\d{6}), '
                                 'sync threadpool max workers: '
                                 f'{self._default_workers}'
                                 )

    async def test_async_invocation_request_log(self):
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with self._ctrl as host:
                await host.init_worker()
                request_id: str = self._ctrl._worker._request_id
                func_id, invoke_id, func_name = (
                    await self._check_if_async_function_is_ok(host)
                )

                logs, _ = mock_logger.info.call_args
                self.assertRegex(logs[0],
                                 'Received FunctionInvocationRequest, '
                                 f'request ID: {request_id}, '
                                 f'function ID: {func_id}, '
                                 f'function name: {func_name}, '
                                 f'invocation ID: {invoke_id}, '
                                 'function type: async, '
                                 r'timestamp \(UTC\): '
                                 r'(\d{4}-\d{2}-\d{2} '
                                 r'\d{2}:\d{2}:\d{2}.\d{6})'
                                 )

    async def test_sync_invocation_request_log_threads(self):
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '5'})

            async with self._ctrl as host:
                await host.init_worker()
                request_id: str = self._ctrl._worker._request_id
                func_id, invoke_id, func_name = (
                    await self._check_if_function_is_ok(host)
                )

                logs, _ = mock_logger.info.call_args
                self.assertRegex(logs[0],
                                 'Received FunctionInvocationRequest, '
                                 f'request ID: {request_id}, '
                                 f'function ID: {func_id}, '
                                 f'function name: {func_name}, '
                                 f'invocation ID: {invoke_id}, '
                                 'function type: sync, '
                                 r'timestamp \(UTC\): '
                                 r'(\d{4}-\d{2}-\d{2} '
                                 r'\d{2}:\d{2}:\d{2}.\d{6}), '
                                 'sync threadpool max workers: 5'
                                 )

    async def test_async_invocation_request_log_threads(self):
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '4'})

            async with self._ctrl as host:
                await host.init_worker()
                request_id: str = self._ctrl._worker._request_id
                func_id, invoke_id, func_name = (
                    await self._check_if_async_function_is_ok(host)
                )

                logs, _ = mock_logger.info.call_args
                self.assertRegex(logs[0],
                                 'Received FunctionInvocationRequest, '
                                 f'request ID: {request_id}, '
                                 f'function ID: {func_id}, '
                                 f'function name: {func_name}, '
                                 f'invocation ID: {invoke_id}, '
                                 'function type: async, '
                                 r'timestamp \(UTC\): '
                                 r'(\d{4}-\d{2}-\d{2} '
                                 r'\d{2}:\d{2}:\d{2}.\d{6})'
                                 )

    async def test_sync_invocation_request_log_in_placeholder_threads(self):
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with self._ctrl as host:
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '5'
                })

                request_id: str = self._ctrl._worker._request_id
                func_id, invoke_id, func_name = (
                    await self._check_if_function_is_ok(host)
                )

                logs, _ = mock_logger.info.call_args
                self.assertRegex(logs[0],
                                 'Received FunctionInvocationRequest, '
                                 f'request ID: {request_id}, '
                                 f'function ID: {func_id}, '
                                 f'function name: {func_name}, '
                                 f'invocation ID: {invoke_id}, '
                                 'function type: sync, '
                                 r'timestamp \(UTC\): '
                                 r'(\d{4}-\d{2}-\d{2} '
                                 r'\d{2}:\d{2}:\d{2}.\d{6}), '
                                 'sync threadpool max workers: 5'
                                 )

    async def test_async_invocation_request_log_in_placeholder_threads(self):
        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with self._ctrl as host:
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '5'
                })

                request_id: str = self._ctrl._worker._request_id
                func_id, invoke_id, func_name = (
                    await self._check_if_async_function_is_ok(host)
                )

                logs, _ = mock_logger.info.call_args
                self.assertRegex(logs[0],
                                 'Received FunctionInvocationRequest, '
                                 f'request ID: {request_id}, '
                                 f'function ID: {func_id}, '
                                 f'function name: {func_name}, '
                                 f'invocation ID: {invoke_id}, '
                                 'function type: async, '
                                 r'timestamp \(UTC\): '
                                 r'(\d{4}-\d{2}-\d{2} '
                                 r'\d{2}:\d{2}:\d{2}.\d{6})'
                                 )

    async def _assert_workers_threadpool(self, ctrl, host,
                                         expected_worker_count):
        self.assertIsNotNone(ctrl._worker._sync_call_tp)
        self.assertEqual(ctrl._worker.get_sync_tp_workers_set(),
                         expected_worker_count)
        # Check if the dispatcher still function
        await self._check_if_function_is_ok(host)

    async def _check_if_function_is_ok(self, host) -> Tuple[str, str, str]:
        # Ensure the function can be properly loaded
        function_name = "show_context"
        func_id, load_r = await host.load_function(function_name)
        self.assertEqual(load_r.response.function_id, func_id)
        ex = load_r.response.result.exception
        self.assertEqual(load_r.response.result.status,
                         protos.StatusResult.Success, msg=ex)

        # Ensure the function can be properly invoked
        invoke_id, call_r = await host.invoke_function(
            'show_context', [
                protos.ParameterBinding(
                    name='req',
                    data=protos.TypedData(
                        http=protos.RpcHttp(
                            method='GET'
                        )
                    )
                )
            ])
        self.assertIsNotNone(invoke_id)
        self.assertEqual(call_r.response.result.status,
                         protos.StatusResult.Success)

        return func_id, invoke_id, function_name

    async def _check_if_async_function_is_ok(self, host) -> Tuple[str, str]:
        # Ensure the function can be properly loaded
        function_name = "show_context_async"
        func_id, load_r = await host.load_function('show_context_async')
        self.assertEqual(load_r.response.function_id, func_id)
        self.assertEqual(load_r.response.result.status,
                         protos.StatusResult.Success)

        # Ensure the function can be properly invoked
        invoke_id, call_r = await host.invoke_function(
            'show_context_async', [
                protos.ParameterBinding(
                    name='req',
                    data=protos.TypedData(
                        http=protos.RpcHttp(
                            method='GET'
                        )
                    )
                )
            ])
        self.assertIsNotNone(invoke_id)
        self.assertEqual(call_r.response.result.status,
                         protos.StatusResult.Success)

        return func_id, invoke_id, function_name


@unittest.skipIf(sys.version_info.minor != 8,
                 "Run the tests only for Python 3.8. In other platforms, "
                 "as the default passed is None, the cpu_count determines the "
                 "number of max_workers and we cannot mock the os.cpu_count() "
                 "in the concurrent.futures.ThreadPoolExecutor")
class TestThreadPoolSettingsPython38(TestThreadPoolSettingsPython37):
    def setUp(self, version=SysVersionInfo(3, 8, 0, 'final', 0)):
        super(TestThreadPoolSettingsPython38, self).setUp(version)
        self._allowed_max_workers: int = self._over_max_workers

    def tearDown(self):
        super(TestThreadPoolSettingsPython38, self).tearDown()

    async def test_dispatcher_sync_threadpool_in_placeholder_above_max(self):
        """Test if the sync threadpool will use any value and there isn't any
        artificial max value set.
        """
        with patch('azure_functions_worker.dispatcher.logger'):
            async with self._ctrl as host:
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: f'{self._over_max_workers}'
                })
                await self._assert_workers_threadpool(self._ctrl, host,
                                                      self._allowed_max_workers)
                self.assertNotEqual(
                    self._ctrl._worker.get_sync_tp_workers_set(),
                    self._default_workers)


@unittest.skipIf(sys.version_info.minor != 9,
                 "Run the tests only for Python 3.9. In other platforms, "
                 "as the default passed is None, the cpu_count determines the "
                 "number of max_workers and we cannot mock the os.cpu_count() "
                 "in the concurrent.futures.ThreadPoolExecutor")
class TestThreadPoolSettingsPython39(TestThreadPoolSettingsPython38):
    def setUp(self, version=SysVersionInfo(3, 9, 0, 'final', 0)):
        super(TestThreadPoolSettingsPython39, self).setUp(version)

        self.mock_os_cpu = patch(
            'os.cpu_count', return_value=2)
        # 6 - based on 2 cores - min(32, (os.cpu_count() or 1) + 4) - 2 + 4
        self._default_workers: Optional[int] = 6
        self.mock_os_cpu.start()

    def tearDown(self):
        self.mock_os_cpu.stop()
        super(TestThreadPoolSettingsPython39, self).tearDown()


@unittest.skipIf(sys.version_info.minor != 10,
                 "Run the tests only for Python 3.10. In other platforms, "
                 "as the default passed is None, the cpu_count determines the "
                 "number of max_workers and we cannot mock the os.cpu_count() "
                 "in the concurrent.futures.ThreadPoolExecutor")
class TestThreadPoolSettingsPython310(TestThreadPoolSettingsPython39):
    def setUp(self, version=SysVersionInfo(3, 10, 0, 'final', 0)):
        super(TestThreadPoolSettingsPython310, self).setUp(version)

    def tearDown(self):
        super(TestThreadPoolSettingsPython310, self).tearDown()


@unittest.skipIf(sys.version_info.minor != 11,
                 "Run the tests only for Python 3.11. In other platforms, "
                 "as the default passed is None, the cpu_count determines the "
                 "number of max_workers and we cannot mock the os.cpu_count() "
                 "in the concurrent.futures.ThreadPoolExecutor")
class TestThreadPoolSettingsPython311(TestThreadPoolSettingsPython310):
    def setUp(self, version=SysVersionInfo(3, 11, 0, 'final', 0)):
        super(TestThreadPoolSettingsPython311, self).setUp(version)

    def tearDown(self):
        super(TestThreadPoolSettingsPython310, self).tearDown()


class TestDispatcherStein(testutils.AsyncTestCase):

    def setUp(self):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_STEIN_FUNCTIONS_DIR)

    async def test_dispatcher_functions_metadata_request(self):
        """Test if the functions metadata response will be sent correctly
        when a functions metadata request is received
        """
        async with self._ctrl as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertFalse(r.response.use_default_metadata_indexing)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

    async def test_dispatcher_functions_metadata_request_with_retry(self):
        """Test if the functions metadata response will be sent correctly
        when a functions metadata request is received
        """
        async with self._ctrl as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertFalse(r.response.use_default_metadata_indexing)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)


class TestDispatcherSteinLegacyFallback(testutils.AsyncTestCase):

    def setUp(self):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_FUNCTIONS_DIR)
        self._pre_env = dict(os.environ)
        self.mock_version_info = patch(
            'azure_functions_worker.dispatcher.sys.version_info',
            SysVersionInfo(3, 9, 0, 'final', 0))
        self.mock_version_info.start()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_dispatcher_functions_metadata_request_legacy_fallback(self):
        """Test if the functions metadata response will be sent correctly
        when a functions metadata request is received
        """
        async with self._ctrl as host:
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertTrue(r.response.use_default_metadata_indexing)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)


class TestDispatcherInitRequest(testutils.AsyncTestCase):

    def setUp(self):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_FUNCTIONS_DIR)
        self._pre_env = dict(os.environ)
        self.mock_version_info = patch(
            'azure_functions_worker.dispatcher.sys.version_info',
            SysVersionInfo(3, 9, 0, 'final', 0))
        self.mock_version_info.start()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_dispatcher_load_azfunc_in_init(self):
        """Test if azure functions is loaded during init
        """
        async with self._ctrl as host:
            r = await host.init_worker()
            self.assertEqual(
                len([log for log in r.logs if log.message.startswith(
                    'Received WorkerInitRequest'
                )]),
                1
            )
            self.assertEqual(
                len([log for log in r.logs if log.message.startswith(
                    "Received WorkerMetadataRequest from "
                    "_handle__worker_init_request"
                )]),
                0
            )
        self.assertIn("azure.functions", sys.modules)

    async def test_dispatcher_indexing_in_init_request(self):
        """Test if azure functions is loaded during init
        """
        env = {PYTHON_ENABLE_INIT_INDEXING: "1",
               PYTHON_ENABLE_DEBUG_LOGGING: "1"}
        with patch.dict(os.environ, env):
            async with self._ctrl as host:
                r = await host.init_worker()
                self.assertEqual(
                    len([log for log in r.logs if log.message.startswith(
                        "Received WorkerInitRequest"
                    )]),
                    1
                )

                self.assertEqual(
                    len([log for log in r.logs if log.message.startswith(
                        "Received load metadata request from "
                        "worker_init_request"
                    )]),
                    1
                )

    async def test_dispatcher_load_modules_dedicated_app(self):
        """Test modules are loaded in dedicated apps
        """
        os.environ["PYTHON_ISOLATE_WORKER_DEPENDENCIES"] = "1"

        # Dedicated Apps where placeholder mode is not set
        async with self._ctrl as host:
            r = await host.init_worker()
            logs = [log.message for log in r.logs]
            self.assertIn(
                "Applying prioritize_customer_dependencies: "
                "worker_dependencies_path: , customer_dependencies_path: , "
                "working_directory: , Linux Consumption: False,"
                " Placeholder: False", logs
            )

    async def test_dispatcher_load_modules_con_placeholder_enabled(self):
        """Test modules are loaded in consumption apps with placeholder mode
        enabled.
        """
        # Consumption apps with placeholder mode enabled
        os.environ["PYTHON_ISOLATE_WORKER_DEPENDENCIES"] = "1"
        os.environ["CONTAINER_NAME"] = "test"
        os.environ["WEBSITE_PLACEHOLDER_MODE"] = "1"
        async with self._ctrl as host:
            r = await host.init_worker()
            logs = [log.message for log in r.logs]
            self.assertNotIn(
                "Applying prioritize_customer_dependencies: "
                "worker_dependencies_path: , customer_dependencies_path: , "
                "working_directory: , Linux Consumption: True,", logs)

    async def test_dispatcher_load_modules_con_app_placeholder_disabled(self):
        """Test modules are loaded in consumption apps with placeholder mode
        disabled.
        """
        # Consumption apps with placeholder mode disabled  i.e. worker
        # is specialized
        os.environ["PYTHON_ISOLATE_WORKER_DEPENDENCIES"] = "1"
        os.environ["WEBSITE_PLACEHOLDER_MODE"] = "0"
        os.environ["CONTAINER_NAME"] = "test"
        async with self._ctrl as host:
            r = await host.init_worker()
            logs = [log.message for log in r.logs]
            self.assertIn(
                "Applying prioritize_customer_dependencies: "
                "worker_dependencies_path: , customer_dependencies_path: , "
                "working_directory: , Linux Consumption: True,"
                " Placeholder: False", logs)


class TestDispatcherIndexinginInit(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.dispatcher = testutils.create_dummy_dispatcher()
        sys.path.append(str(FUNCTION_APP_DIRECTORY))

    def tearDown(self):
        self.loop.close()

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'true'})
    def test_worker_init_request_with_indexing_enabled(self):
        request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(request))

        self.assertIsNotNone(self.dispatcher._function_metadata_result)
        self.assertIsNone(self.dispatcher._function_metadata_exception)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'false'})
    def test_worker_init_request_with_indexing_disabled(self):
        request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(request))

        self.assertIsNone(self.dispatcher._function_metadata_result)
        self.assertIsNone(self.dispatcher._function_metadata_exception)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'true'})
    @patch.object(Dispatcher, 'index_functions')
    def test_worker_init_request_with_indexing_exception(self,
                                                         mock_index_functions):
        mock_index_functions.side_effect = Exception("Mocked Exception")

        request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(request))

        self.assertIsNone(self.dispatcher._function_metadata_result)
        self.assertIsNotNone(self.dispatcher._function_metadata_exception)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'true'})
    def test_functions_metadata_request_with_init_indexing_enabled(self):
        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        metadata_request = protos.StreamingMessage(
            functions_metadata_request=protos.FunctionsMetadataRequest(
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))
        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        metadata_response = self.loop.run_until_complete(
            self.dispatcher._handle__functions_metadata_request(
                metadata_request))

        self.assertEqual(
            metadata_response.function_metadata_response.result.status,
            protos.StatusResult.Success)
        self.assertIsNotNone(self.dispatcher._function_metadata_result)
        self.assertIsNone(self.dispatcher._function_metadata_exception)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'false'})
    def test_functions_metadata_request_with_init_indexing_disabled(self):
        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        metadata_request = protos.StreamingMessage(
            functions_metadata_request=protos.FunctionsMetadataRequest(
                function_app_directory=str(str(FUNCTION_APP_DIRECTORY))
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))
        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)
        self.assertIsNone(self.dispatcher._function_metadata_result)
        self.assertIsNone(self.dispatcher._function_metadata_exception)

        metadata_response = self.loop.run_until_complete(
            self.dispatcher._handle__functions_metadata_request(
                metadata_request))

        self.assertEqual(
            metadata_response.function_metadata_response.result.status,
            protos.StatusResult.Success)
        self.assertIsNotNone(self.dispatcher._function_metadata_result)
        self.assertIsNone(self.dispatcher._function_metadata_exception)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'true'})
    @patch.object(Dispatcher, 'index_functions')
    def test_functions_metadata_request_with_indexing_exception(
            self,
            mock_index_functions):
        mock_index_functions.side_effect = Exception("Mocked Exception")

        request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        metadata_request = protos.StreamingMessage(
            functions_metadata_request=protos.FunctionsMetadataRequest(
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(request))

        self.assertIsNone(self.dispatcher._function_metadata_result)
        self.assertIsNotNone(self.dispatcher._function_metadata_exception)

        metadata_response = self.loop.run_until_complete(
            self.dispatcher._handle__functions_metadata_request(
                metadata_request))

        self.assertEqual(
            metadata_response.function_metadata_response.result.status,
            protos.StatusResult.Failure)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'false'})
    def test_dispatcher_indexing_in_load_request(self):
        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertIsNone(self.dispatcher._function_metadata_result)

        load_request = protos.StreamingMessage(
            function_load_request=protos.FunctionLoadRequest(
                function_id="http_trigger",
                metadata=protos.RpcFunctionMetadata(
                    directory=str(FUNCTION_APP_DIRECTORY),
                    properties={METADATA_PROPERTIES_WORKER_INDEXED: "True"}
                )))

        self.loop.run_until_complete(
            self.dispatcher._handle__function_load_request(load_request))

        self.assertIsNotNone(self.dispatcher._function_metadata_result)
        self.assertIsNone(self.dispatcher._function_metadata_exception)

    @patch.dict(os.environ, {PYTHON_ENABLE_INIT_INDEXING: 'true'})
    @patch.object(Dispatcher, 'index_functions')
    def test_dispatcher_indexing_in_load_request_with_exception(
            self,
            mock_index_functions):
        # This is the case when the second worker has an exception in indexing.
        # In this case, we save the error in _function_metadata_exception in
        # the init request and throw the error when load request is called.

        mock_index_functions.side_effect = Exception("Mocked Exception")

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertIsNone(self.dispatcher._function_metadata_result)

        load_request = protos.StreamingMessage(
            function_load_request=protos.FunctionLoadRequest(
                function_id="http_trigger",
                metadata=protos.RpcFunctionMetadata(
                    directory=str(FUNCTION_APP_DIRECTORY),
                    properties={METADATA_PROPERTIES_WORKER_INDEXED: "True"}
                )))

        response = self.loop.run_until_complete(
            self.dispatcher._handle__function_load_request(load_request))

        self.assertIsNotNone(self.dispatcher._function_metadata_exception)
        self.assertEqual(
            response.function_load_response.result.exception.message,
            "Exception: Mocked Exception")


class TestContextEnabledTask(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_init_with_context(self):
        num = contextvars.ContextVar('num')
        num.set(5)
        ctx = contextvars.copy_context()
        exception_raised = False
        try:
            self.loop.set_task_factory(
                lambda loop, coro, context=None: ContextEnabledTask(
                    coro, loop=loop, context=ctx))
        except TypeError:
            exception_raised = True
        self.assertFalse(exception_raised)

    async def test_init_without_context(self):
        exception_raised = False
        try:
            self.loop.set_task_factory(
                lambda loop, coro: ContextEnabledTask(
                    coro, loop=loop))
        except TypeError:
            exception_raised = True
        self.assertFalse(exception_raised)
