import json

from azure.functions_worker import protos
from azure.functions_worker import testutils


class TestEventHubMockFunctions(testutils.AsyncTestCase):

    async def test_mock_eventhub_trigger_iot(self):
        async with testutils.start_mockhost(
                script_root='unittests/eventhub_mock_functions') as host:

            func_id, r = await host.load_function('eventhub_trigger_iot')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            async def call_and_check():
                _, r = await host.invoke_function(
                    'eventhub_trigger_iot',
                    [
                        protos.ParameterBinding(
                            name='event',
                            data=protos.TypedData(
                                json=json.dumps({
                                    'id': 'foo'
                                })
                            ),
                        ),
                    ],
                    metadata={
                        'iothub-device-id': protos.TypedData(
                            string='mock-iothub-device-id'
                        ),
                        'iothub-auth-data': protos.TypedData(
                            string='mock-iothub-auth-data'
                        )
                    }
                )

                self.assertEqual(r.response.result.status,
                                 protos.StatusResult.Success)
                self.assertIn(
                    'mock-iothub-device-id',
                    r.response.return_value.string
                )

            await call_and_check()
