import os
import asyncio

from azure.functions_worker import protos
from azure.functions_worker import dispatcher
from azure.functions_worker import testutils


class TestGRPC(testutils.AsyncTestCase):
    pre_test_env = os.environ.copy()

    async def _handle_environment_reload_request(self, test_env):
            request = protos.FunctionEnvironmentReloadRequest(
                environment_variables=test_env)

            request_msg = protos.StreamingMessage(
                request_id='0',
                function_environment_reload_request=request)

            dummy_event_loop = asyncio.new_event_loop()
            disp = dispatcher.Dispatcher(
                dummy_event_loop, '127.0.0.1', 0,
                'test_worker_id', 'test_request_id',
                1.0, 1000)
            dummy_event_loop.close()

            try:
                r = await disp._handle__function_environment_reload_request(
                    request_msg)

                environ_dict = os.environ.copy()
                self.assertDictEqual(environ_dict, test_env)
                status = r.function_environment_reload_response.result.status
                self.assertEqual(status, protos.StatusResult.Success)
            finally:
                self.reset_environ()

    async def test_multiple_env_vars_load(self):
        test_env = {'TEST_KEY': 'foo', 'HELLO': 'world'}
        await self._handle_environment_reload_request(test_env)

    async def test_empty_env_vars_load(self):
        test_env = {}
        await self._handle_environment_reload_request(test_env)

    def reset_environ(self):
        for key, value in self.pre_test_env.items():
            os.environ[key] = value
