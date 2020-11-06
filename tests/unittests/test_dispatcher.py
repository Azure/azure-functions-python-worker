# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Tuple
import os
from unittest.mock import patch
from azure_functions_worker import protos
from azure_functions_worker import testutils
from azure_functions_worker.constants import PYTHON_THREADPOOL_THREAD_COUNT


class TestDispatcher(testutils.AsyncTestCase):
    dispatcher_funcs_dir = testutils.UNIT_TESTS_FOLDER / 'dispatcher_functions'

    def setUp(self):
        self._pre_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)

    async def test_dispatcher_sync_threadpool_default_worker(self):
        """Test if the sync threadpool has maximum worker count set to 1
        by default
        """
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
            self.assertIsNotNone(ctrl._worker._sync_call_tp)

            # Check if the dispatcher still function
            await self._check_if_function_is_ok(host)

    async def test_dispatcher_sync_threadpool_set_worker(self):
        """Test if the sync threadpool maximum worker can be set
        """
        # Configure thread pool max worker
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '5'})
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 5)
            self.assertIsNotNone(ctrl._worker._sync_call_tp)

            # Check if the dispatcher still function
            await self._check_if_function_is_ok(host)

    async def test_dispatcher_sync_threadpool_invalid_worker_count(self):
        """Test when sync threadpool maximum worker is set to an invalid value,
        the host should fallback to default value 1
        """
        # The @patch decorator does not work as expected and will suppress
        # any assertion failures in the async test cases.
        # Thus we're moving the patch() method to use the with syntax

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            # Configure thread pool max worker to an invalid value
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: 'invalid'})
            ctrl = testutils.start_mockhost(
                script_root=self.dispatcher_funcs_dir)

            async with ctrl as host:
                await self._check_if_function_is_ok(host)

                # Ensure the dispatcher sync threadpool should fallback to 1
                self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
                self.assertIsNotNone(ctrl._worker._sync_call_tp)

                # Check if the dispatcher still function
                await self._check_if_function_is_ok(host)

            mock_logger.warning.assert_any_call(
                f'{PYTHON_THREADPOOL_THREAD_COUNT} must be an integer')

    async def test_dispatcher_sync_threadpool_below_min_setting(self):
        """Test if the sync threadpool will pick up default value when the
        setting is below minimum
        """

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            # Configure thread pool max worker to an invalid value
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '0'})
            ctrl = testutils.start_mockhost(
                script_root=self.dispatcher_funcs_dir)

            async with ctrl as host:
                await self._check_if_function_is_ok(host)

                # Ensure the dispatcher sync threadpool should fallback to 1
                self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
                self.assertIsNotNone(ctrl._worker._sync_call_tp)

                # Check if the dispatcher still function
                await self._check_if_function_is_ok(host)

            mock_logger.warning.assert_any_call(
                f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set to a value '
                'between 1 and 32')

    async def test_dispatcher_sync_threadpool_exceed_max_setting(self):
        """Test if the sync threadpool will pick up default value when the
        setting is above maximum
        """

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            # Configure thread pool max worker to an invalid value
            os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '33'})
            ctrl = testutils.start_mockhost(
                script_root=self.dispatcher_funcs_dir)

            async with ctrl as host:
                await self._check_if_function_is_ok(host)

                # Ensure the dispatcher sync threadpool should fallback to 1
                self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
                self.assertIsNotNone(ctrl._worker._sync_call_tp)

                # Check if the dispatcher still function
                await self._check_if_function_is_ok(host)

            mock_logger.warning.assert_any_call(
                f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set to a value '
                'between 1 and 32')

    async def test_dispatcher_sync_threadpool_in_placeholder(self):
        """Test if the sync threadpool will pick up app setting in placeholder
        mode (Linux Consumption)
        """

        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)

            # Reload environment variable on specialization
            await host.reload_environment(environment={
                PYTHON_THREADPOOL_THREAD_COUNT: '3'
            })

            # Ensure the dispatcher sync threadpool should update to 3
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 3)
            self.assertIsNotNone(ctrl._worker._sync_call_tp)

            # Check if the dispatcher still function
            await self._check_if_function_is_ok(host)

    async def test_dispatcher_sync_threadpool_in_placeholder_invalid(self):
        """Test if the sync threadpool will use the default setting when the
        app setting is invalid
        """

        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: 'invalid'
                })

                # Ensure the dispatcher sync threadpool should fallback to 1
                self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
                self.assertIsNotNone(ctrl._worker._sync_call_tp)

                # Check if the dispatcher still function
                await self._check_if_function_is_ok(host)

                # Check warning message
                mock_logger.warning.assert_any_call(
                    f'{PYTHON_THREADPOOL_THREAD_COUNT} must be an integer')

    async def test_dispatcher_sync_threadpool_in_placeholder_above_max(self):
        """Test if the sync threadpool will use the default setting when the
        app setting is above maximum
        """

        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '33'
                })

                # Ensure the dispatcher sync threadpool should fallback to 1
                self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
                self.assertIsNotNone(ctrl._worker._sync_call_tp)

                # Check if the dispatcher still function
                await self._check_if_function_is_ok(host)

                # Check warning message
                mock_logger.warning.assert_any_call(
                    f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set to a value '
                    'between 1 and 32')

    async def test_dispatcher_sync_threadpool_in_placeholder_below_min(self):
        """Test if the sync threadpool will use the default setting when the
        app setting is below minimum
        """

        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                await self._check_if_function_is_ok(host)

                # Reload environment variable on specialization
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '0'
                })

                # Ensure the dispatcher sync threadpool should fallback to 1
                self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)
                self.assertIsNotNone(ctrl._worker._sync_call_tp)

                # Check if the dispatcher still function
                await self._check_if_function_is_ok(host)

                # Check warning message
                mock_logger.warning.assert_any_call(
                    f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set to a value '
                    'between 1 and 32')

    async def test_sync_invocation_request_log(self):
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                request_id: str = ctrl._worker._request_id
                func_id, invoke_id = await self._check_if_function_is_ok(host)

                mock_logger.info.assert_any_call(
                    'Received FunctionInvocationRequest, '
                    f'request ID: {request_id}, '
                    f'function ID: {func_id}, '
                    f'invocation ID: {invoke_id}, '
                    'function type: sync, '
                    'sync threadpool max workers: 1'
                )

    async def test_async_invocation_request_log(self):
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                request_id: str = ctrl._worker._request_id
                func_id, invoke_id = (
                    await self._check_if_async_function_is_ok(host)
                )

                mock_logger.info.assert_any_call(
                    'Received FunctionInvocationRequest, '
                    f'request ID: {request_id}, '
                    f'function ID: {func_id}, '
                    f'invocation ID: {invoke_id}, '
                    'function type: async'
                )

    async def test_sync_invocation_request_log_threads(self):
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '5'})

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                request_id: str = ctrl._worker._request_id
                func_id, invoke_id = await self._check_if_function_is_ok(host)

                mock_logger.info.assert_any_call(
                    'Received FunctionInvocationRequest, '
                    f'request ID: {request_id}, '
                    f'function ID: {func_id}, '
                    f'invocation ID: {invoke_id}, '
                    'function type: sync, '
                    'sync threadpool max workers: 5'
                )

    async def test_async_invocation_request_log_threads(self):
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '4'})

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                request_id: str = ctrl._worker._request_id
                func_id, invoke_id = (
                    await self._check_if_async_function_is_ok(host)
                )

                mock_logger.info.assert_any_call(
                    'Received FunctionInvocationRequest, '
                    f'request ID: {request_id}, '
                    f'function ID: {func_id}, '
                    f'invocation ID: {invoke_id}, '
                    'function type: async'
                )

    async def test_sync_invocation_request_log_in_placeholder_threads(self):
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '5'
                })

                request_id: str = ctrl._worker._request_id
                func_id, invoke_id = await self._check_if_function_is_ok(host)

                mock_logger.info.assert_any_call(
                    'Received FunctionInvocationRequest, '
                    f'request ID: {request_id}, '
                    f'function ID: {func_id}, '
                    f'invocation ID: {invoke_id}, '
                    'function type: sync, '
                    'sync threadpool max workers: 5'
                )

    async def test_async_invocation_request_log_in_placeholder_threads(self):
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        with patch('azure_functions_worker.dispatcher.logger') as mock_logger:
            async with ctrl as host:
                await host.reload_environment(environment={
                    PYTHON_THREADPOOL_THREAD_COUNT: '5'
                })

                request_id: str = ctrl._worker._request_id
                func_id, invoke_id = (
                    await self._check_if_async_function_is_ok(host)
                )

                mock_logger.info.assert_any_call(
                    'Received FunctionInvocationRequest, '
                    f'request ID: {request_id}, '
                    f'function ID: {func_id}, '
                    f'invocation ID: {invoke_id}, '
                    'function type: async'
                )

    async def _check_if_function_is_ok(self, host) -> Tuple[str, str]:
        # Ensure the function can be properly loaded
        func_id, load_r = await host.load_function('show_context')
        self.assertEqual(load_r.response.function_id, func_id)
        self.assertEqual(load_r.response.result.status,
                         protos.StatusResult.Success)

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

        return (func_id, invoke_id)

    async def _check_if_async_function_is_ok(self, host) -> Tuple[str, str]:
        # Ensure the function can be properly loaded
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

        return (func_id, invoke_id)
