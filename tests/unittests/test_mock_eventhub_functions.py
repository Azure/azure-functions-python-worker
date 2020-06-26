# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestEventHubMockFunctions(testutils.AsyncTestCase):
    mock_funcs_dir = testutils.UNIT_TESTS_FOLDER / 'eventhub_mock_functions'

    async def test_mock_eventhub_trigger_iot(self):
        async with testutils.start_mockhost(
                script_root=self.mock_funcs_dir) as host:

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
                        'SystemProperties': protos.TypedData(json=json.dumps({
                            'iothub-device-id': 'mock-iothub-device-id',
                            'iothub-auth-data': 'mock-iothub-auth-data',
                            'EnqueuedTimeUtc': '2020-02-18T21:28:42.5888539Z'
                        }))
                    }
                )

                self.assertEqual(r.response.result.status,
                                 protos.StatusResult.Success)

                res_json_string = r.response.return_value.string
                self.assertIn('device-id', res_json_string)
                self.assertIn('mock-iothub-device-id', res_json_string)
                self.assertIn('auth-data', res_json_string)
                self.assertIn('mock-iothub-auth-data', res_json_string)

            await call_and_check()

    async def test_mock_eventhub_cardinality_one(self):
        async with testutils.start_mockhost(
                script_root=self.mock_funcs_dir) as host:

            func_id, r = await host.load_function('eventhub_cardinality_one')
            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'eventhub_cardinality_one',
                [
                    protos.ParameterBinding(
                        name='event',
                        data=protos.TypedData(
                            json=json.dumps({
                                'id': 'cardinality_one'
                            })
                        ),
                    ),
                ],
                metadata={
                    'SystemProperties': protos.TypedData(json=json.dumps({
                        'iothub-device-id': 'mock-iothub-device-id',
                        'iothub-auth-data': 'mock-iothub-auth-data',
                        'EnqueuedTimeUtc': '2020-02-18T21:28:42.5888539Z'
                    }))
                }
            )

            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(r.response.return_value.string, 'OK_ONE')

    async def test_mock_eventhub_cardinality_one_bad_annotation(self):
        async with testutils.start_mockhost(
                script_root=self.mock_funcs_dir) as host:

            # This suppose to fail since the event should not be int
            func_id, r = await host.load_function(
                'eventhub_cardinality_one_bad_anno'
            )
            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

    async def test_mock_eventhub_cardinality_many(self):
        async with testutils.start_mockhost(
                script_root=self.mock_funcs_dir) as host:

            func_id, r = await host.load_function('eventhub_cardinality_many')
            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'eventhub_cardinality_many',
                [
                    protos.ParameterBinding(
                        name='events',
                        data=protos.TypedData(
                            json=json.dumps([{
                                'id': 'cardinality_many'
                            }])
                        ),
                    ),
                ],
                metadata={
                    'SystemPropertiesArray': protos.TypedData(json=json.dumps([
                        {
                            'iothub-device-id': 'mock-iothub-device-id',
                            'iothub-auth-data': 'mock-iothub-auth-data',
                            'EnqueuedTimeUtc': '2020-02-18T21:28:42.5888539Z'
                        }
                    ]))
                }
            )

            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(r.response.return_value.string, 'OK_MANY')

    async def test_mock_eventhub_cardinality_many_bad_annotation(self):
        async with testutils.start_mockhost(
                script_root=self.mock_funcs_dir) as host:

            # This suppose to fail since the event should not be List[str]
            func_id, r = await host.load_function(
                'eventhub_cardinality_many_bad_anno'
            )
            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)
