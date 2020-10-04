# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestMockHost(testutils.AsyncTestCase):

    async def test_call_sync_function_check_logs(self):
        async with testutils.start_mockhost() as host:
            await host.load_function('sync_logging')

            invoke_id, r = await host.invoke_function(
                'sync_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET')))
                ])

            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            user_logs = [line for line in r.logs
                         if line.category == 'my function']
            # 2 log statements added (critical and error) in sync_logging
            self.assertEqual(len(user_logs), 2)

            log = user_logs[0]
            self.assertEqual(log.invocation_id, invoke_id)
            self.assertTrue(log.message.startswith(
                'a gracefully handled error'))

            self.assertEqual(r.response.return_value.string, 'OK-sync')

    async def test_call_async_function_check_logs(self):
        async with testutils.start_mockhost() as host:
            await host.load_function('async_logging')

            invoke_id, r = await host.invoke_function(
                'async_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET')))
                ])

            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            user_logs = [line for line in r.logs if
                         line.category == 'my function']
            self.assertEqual(len(user_logs), 2)

            first_msg = user_logs[0]
            self.assertEqual(first_msg.invocation_id, invoke_id)
            self.assertEqual(first_msg.message, 'hello info')
            self.assertEqual(first_msg.level, protos.RpcLog.Information)

            second_msg = user_logs[1]
            self.assertEqual(second_msg.invocation_id, invoke_id)
            self.assertTrue(second_msg.message.startswith('and another error'))
            self.assertEqual(second_msg.level, protos.RpcLog.Error)

            self.assertEqual(r.response.return_value.string, 'OK-async')

    async def test_handles_unsupported_messages_gracefully(self):
        async with testutils.start_mockhost() as host:
            # Intentionally send a message to worker that isn't
            # going to be ever supported by it.  The idea is that
            # workers should survive such messages and continue
            # their operation.  If anything, the host can always
            # terminate the worker.
            await host.send(
                protos.StreamingMessage(
                    worker_heartbeat=protos.WorkerHeartbeat()))

            _, r = await host.load_function('return_out')
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
