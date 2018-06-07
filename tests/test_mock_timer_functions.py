import json

from azure.functions_worker import protos
from azure.functions_worker import testutils


class TestTimerFunctions(testutils.AsyncTestCase):

    async def test_mock_timer__return_pastdue(self):
        async with testutils.start_mockhost(
                script_root='timer_functions') as host:

            func_id, r = await host.load_function('return_pastdue')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            async def call_and_check(due: bool):
                _, r = await host.invoke_function(
                    'return_pastdue', [
                        protos.ParameterBinding(
                            name='timer',
                            data=protos.TypedData(
                                json=json.dumps({
                                    'IsPastDue': due
                                })))
                    ])
                self.assertEqual(r.response.result.status,
                                 protos.StatusResult.Success)
                self.assertEqual(
                    list(r.response.output_data), [
                        protos.ParameterBinding(
                            name='pastdue',
                            data=protos.TypedData(string=str(due)))
                    ])

            await call_and_check(True)
            await call_and_check(False)
