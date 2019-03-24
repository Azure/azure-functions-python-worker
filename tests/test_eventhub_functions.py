import json
import time

from azure.functions_worker import protos
from azure.functions_worker import testutils


class TestEventHubFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'eventhub_functions'

    def test_eventhub_trigger(self):
        data = str(round(time.time()))
        doc = {'id': data}
        r = self.webhost.request('POST', 'eventhub_output',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire.
            time.sleep(2)

            try:
                # Check that the trigger has fired.
                r = self.webhost.request('GET', 'get_eventhub_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(
                    response,
                    doc
                )
            except AssertionError as e:
                if try_no == max_retries - 1:
                    raise
            else:
                break


class TestEventHubMockFunctions(testutils.AsyncTestCase):

    async def test_mock_eventhub_trigger_iot(self):
        async with testutils.start_mockhost(
                script_root='eventhub_functions') as host:

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
