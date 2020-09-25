# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
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
        '''Test if the sync threadpool has maximum worker count set to 1
        by default
        '''
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)

            # Ensure the dispatcher sync threadpool count is set to 1
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)

    async def test_dispatcher_sync_threadpool_set_worker(self):
        '''Test if the sync threadpool maximum worker can be set
        '''
        # Configure thread pool max worker
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '5'})
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)

            # Ensure the dispatcher sync threadpool count is set to 1
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 5)

    @patch('azure_functions_worker.dispatcher.logger')
    async def test_dispatcher_sync_threadpool_invalid_worker_count(
        self,
        mock_logger
    ):
        '''Test when sync threadpool maximum worker is set to an invalid value,
        the host should fallback to default value 1
        '''
        # Configure thread pool max worker to an invalid value
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: 'invalid'})
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)

            # Ensure the dispatcher sync threadpool should fallback to 1
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)

        mock_logger.warning.assert_any_call(
            f'{PYTHON_THREADPOOL_THREAD_COUNT} must be an integer')

    @patch('azure_functions_worker.dispatcher.logger')
    async def test_dispatcher_sync_threadpool_below_min_setting(
        self,
        mock_logger
    ):
        # Configure thread pool max worker to an invalid value
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '0'})
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)

            # Ensure the dispatcher sync threadpool should fallback to 1
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)

        mock_logger.warning.assert_any_call(
            f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set to a value between '
            '1 and 32')

    @patch('azure_functions_worker.dispatcher.logger')
    async def test_dispatcher_sync_threadpool_exceed_max_setting(
        self,
        mock_logger
    ):
        # Configure thread pool max worker to an invalid value
        os.environ.update({PYTHON_THREADPOOL_THREAD_COUNT: '33'})
        ctrl = testutils.start_mockhost(script_root=self.dispatcher_funcs_dir)

        async with ctrl as host:
            await self._check_if_function_is_ok(host)

            # Ensure the dispatcher sync threadpool should fallback to 1
            self.assertEqual(ctrl._worker._sync_tp_max_workers, 1)

        mock_logger.warning.assert_any_call(
            f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set to a value between '
            '1 and 32')

    async def _check_if_function_is_ok(self, host):
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
