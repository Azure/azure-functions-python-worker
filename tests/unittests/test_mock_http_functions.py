# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

from tests.utils import testutils

from azure_functions_worker import protos


class TestMockHost(testutils.AsyncTestCase):

    async def test_call_sync_function_check_logs(self):
        async with testutils.start_mockhost() as host:

            await host.init_worker("4.17.1")
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

            await host.init_worker("4.17.1")
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

            await host.init_worker("4.17.1")
            _, r = await host.load_function('return_out')
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)


class MockHttpFunctions(testutils.AsyncTestCase):
    http_funcs_dir = testutils.UNIT_TESTS_FOLDER / 'http_functions'

    async def test_return_str(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_str')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_str', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='Hello World!'))

    async def test_return_out(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_out')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_out', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            output_data = r.response.output_data[0].data.http
            self.assertEqual(
                output_data.headers['content-type'],
                "text/plain; charset=utf-8")
            self.assertEqual(
                output_data.body.bytes,
                b"hello")
            self.assertEqual(
                output_data.status_code,
                "201")

    async def test_return_bytes(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_bytes')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_bytes', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

    async def test_return_http_200(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_http')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_http', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            http_response = r.response.return_value.http
            self.assertEqual(
                http_response.headers["content-type"],
                "text/html; charset=utf-8")
            self.assertEqual(
                http_response.body.bytes,
                b"<h1>Hello World\342\204\242</h1>")
            self.assertEqual(
                http_response.status_code,
                "200")

    async def test_return_http_no_body(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_http_no_body')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_http_no_body', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            http_response = r.response.return_value.http
            self.assertEqual(
                http_response.body.bytes,
                b"")
            self.assertEqual(
                http_response.status_code,
                "200")

    async def test_return_http_auth_level_admin(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_http_auth_admin')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_http_auth_admin', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET',
                                params={'code': 'testMasterKey'}))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            http_response = r.response.return_value.http
            self.assertEqual(
                http_response.headers["content-type"],
                "text/html; charset=utf-8")
            self.assertEqual(
                http_response.body.bytes,
                b"<h1>Hello World\342\204\242</h1>")
            self.assertEqual(
                http_response.status_code,
                "200")

    async def test_return_http_404(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_http_404')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_http_404', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            http_response = r.response.return_value.http
            self.assertEqual(
                http_response.headers["content-type"],
                "text/plain; charset=utf-8")
            self.assertEqual(
                http_response.body.bytes,
                b"bye")
            self.assertEqual(
                http_response.status_code,
                "404")

    async def test_no_return(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('no_return')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'no_return', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            logs_response = r.logs[1]
            self.assertEqual(
                logs_response.level,
                4)  # Code for logger.error
            self.assertEqual(
                logs_response.message,
                "hi")

    async def test_no_return_returns(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('no_return_returns')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'no_return_returns', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)
            exception = r.response.result.exception.message
            self.assertEqual(
                exception,
                "RuntimeError: function 'no_return_returns' without a $return"
                " bindingreturned a non-None value")

    async def test_async_return_str(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('async_return_str')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'async_return_str', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='Hello Async World!'))

    async def test_async_logging(self):
        # Test that logging doesn't *break* things.
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('async_logging')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'async_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='OK-async'))

            info_log_response = r.logs[1]
            self.assertEqual(
                info_log_response.level,
                2)  # Code for logger.info
            self.assertEqual(
                info_log_response.message,
                "hello info")
            error_log_response = r.logs[2]
            self.assertEqual(
                error_log_response.level,
                4)  # Code for logger.error
            self.assertIn("and another error",
                          error_log_response.message)

    async def test_async_logging(self):
        # Test that logging doesn't *break* things.
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('async_logging')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'async_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='OK-async'))

            info_log_response = r.logs[1]
            self.assertEqual(
                info_log_response.level,
                2)  # Code for logger.info
            self.assertEqual(
                info_log_response.message,
                "hello info")
            error_log_response = r.logs[2]
            self.assertEqual(
                error_log_response.level,
                4)  # Code for logger.error
            self.assertIn("and another error",
                          error_log_response.message)

    async def test_debug_logging(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('debug_logging')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'debug_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='OK-debug'))

            critical_log_response = r.logs[1]
            self.assertEqual(
                critical_log_response.level,
                5)  # Code for logger.info
            self.assertIn("logging critical",
                          critical_log_response.message)
            info_log_response = r.logs[2]
            self.assertEqual(
                info_log_response.level,
                2)  # Code for logger.info
            self.assertIn("logging info",
                          info_log_response.message)
            warning_log_response = r.logs[3]
            self.assertEqual(
                warning_log_response.level,
                3)  # Code for logger.error
            self.assertIn("logging warning",
                          warning_log_response.message)
            error_log_response = r.logs[4]
            self.assertEqual(
                error_log_response.level,
                4)  # Code for logger.error
            self.assertIn("logging error",
                          error_log_response.message)

    async def test_sync_logging(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('sync_logging')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'sync_logging', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='OK-sync'))

            error_log_response = r.logs[1]
            self.assertEqual(
                error_log_response.level,
                4)  # Code for logger.info
            self.assertIn("a gracefully handled error",
                          error_log_response.message)
            error_log_response_2 = r.logs[2]
            self.assertEqual(
                error_log_response_2.level,
                4)  # Code for logger.info
            self.assertIn("a gracefully handled critical error",
                          error_log_response_2.message)

    async def test_return_context(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('return_context')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'return_context', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            data = json.loads(r.response.return_value.string)
            self.assertEqual(data['method'], 'GET')
            self.assertEqual(data['ctx_func_name'], 'return_context')
            self.assertIn('ctx_invocation_id', data)
            self.assertIn('ctx_trace_context_Tracestate', data)
            self.assertIn('ctx_trace_context_Traceparent', data)

    async def test_remapped_context(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('remapped_context')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'remapped_context', [
                    protos.ParameterBinding(
                        name='context',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='GET'))

    async def test_unhandled_error(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('unhandled_error')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'unhandled_error', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)
            self.assertIn("ZeroDivisionError: division by zero",
                          r.response.result.exception.message)

    async def test_unhandled_unserializable_error(self):
        async with testutils.start_mockhost(
                script_root=self.http_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('unhandled_unserializable_error')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'unhandled_unserializable_error', [
                    protos.ParameterBinding(
                        name='req',
                        data=protos.TypedData(
                            http=protos.RpcHttp(
                                method='GET'))
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)
            self.assertIn("Unhandled exception in function."
                          " Could not serialize original exception message.",
                          r.response.result.exception.message)
