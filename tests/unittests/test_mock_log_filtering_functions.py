# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from unittest.mock import patch, call

from azure_functions_worker import testutils, protos
from azure_functions_worker.logging import is_system_log_category


class TestMockLogFilteringFunctions(testutils.AsyncTestCase):
    dir = testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions'

    async def test_root_logger_should_be_customer_log(self):
        """When customer use the root logger to send logs, the 'root' namespace
        should be treated as customer log, only sending to our customers.
        """
        with patch(
            'azure_functions_worker.dispatcher.is_system_log_category'
        ) as islc_mock:
            async with testutils.start_mockhost(script_root=self.dir) as host:
                await host.load_function('debug_logging')
                await self._invoke_function(host, 'debug_logging')

                self.assertIn(call('root'), islc_mock.call_args_list)
                self.assertFalse(is_system_log_category('root'))

    async def test_customer_logging_should_not_be_system_log(self):
        """When sdk uses the 'azure' logger to send logs
        (e.g. 'azure.servicebus'), the namespace should be treated as customer
        log, only sends to our customers.
        """
        with patch(
            'azure_functions_worker.dispatcher.is_system_log_category'
        ) as islc_mock:
            async with testutils.start_mockhost(script_root=self.dir) as host:
                await host.load_function('debug_user_logging')
                await self._invoke_function(host, 'debug_user_logging')

                self.assertIn(call('my function'), islc_mock.call_args_list)
                self.assertFalse(is_system_log_category('my function'))

    async def test_sdk_logger_should_be_system_log(self):
        """When sdk uses the 'azure.functions' logger to send logs, the
        namespace should be treated as system log, sending to our customers and
        our kusto table.
        """
        with patch(
            'azure_functions_worker.dispatcher.is_system_log_category'
        ) as islc_mock:
            async with testutils.start_mockhost(script_root=self.dir) as host:
                await host.load_function('sdk_logging')
                await self._invoke_function(host, 'sdk_logging')

                self.assertIn(
                    call('azure.functions'), islc_mock.call_args_list
                )
                self.assertTrue(is_system_log_category('azure.functions'))

    async def test_sdk_submodule_logger_should_be_system_log(self):
        """When sdk uses the 'azure.functions.submodule' logger to send logs,
        the namespace should be treated as system log, sending to our customers
        and our kusto table.
        """
        with patch(
            'azure_functions_worker.dispatcher.is_system_log_category'
        ) as islc_mock:
            async with testutils.start_mockhost(script_root=self.dir) as host:
                await host.load_function('sdk_submodule_logging')
                await self._invoke_function(host, 'sdk_submodule_logging')

                self.assertIn(
                    call('azure.functions.submodule'), islc_mock.call_args_list
                )
                self.assertTrue(
                    is_system_log_category('azure.functions.submodule')
                )

    async def _invoke_function(self,
                               host: testutils._MockWebHost,
                               function_name: str):
        _, r = await host.invoke_function(
            function_name, [
                protos.ParameterBinding(
                    name='req',
                    data=protos.TypedData(
                        http=protos.RpcHttp(method='GET')
                    )
                )
            ]
        )

        self.assertEqual(r.response.result.status, protos.StatusResult.Success)
