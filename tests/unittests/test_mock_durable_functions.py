# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestDurableFunctions(testutils.AsyncTestCase):
    durable_functions_dir = testutils.UNIT_TESTS_FOLDER / 'durable_functions'

    async def test_mock_activity_trigger(self):
        async with testutils.start_mockhost(
                script_root=self.durable_functions_dir) as host:

            func_id, r = await host.load_function('activity_trigger')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'activity_trigger', [
                    # According to Durable Python
                    # Activity Trigger's input must be json serializable
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            string='test single_word'
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(json='"test single_word"')
            )

    async def test_mock_activity_trigger_no_anno(self):
        async with testutils.start_mockhost(
                script_root=self.durable_functions_dir) as host:

            func_id, r = await host.load_function('activity_trigger_no_anno')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'activity_trigger_no_anno', [
                    # According to Durable Python
                    # Activity Trigger's input must be json serializable
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            string='test multiple words'
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(json='"test multiple words"')
            )

    async def test_mock_activity_trigger_dict(self):
        async with testutils.start_mockhost(
                script_root=self.durable_functions_dir) as host:

            func_id, r = await host.load_function('activity_trigger_dict')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'activity_trigger_dict', [
                    # According to Durable Python
                    # Activity Trigger's input must be json serializable
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            json='{"bird": "Crane"}'
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(json='{"bird": "enarC"}')
            )

    async def test_mock_activity_trigger_int_to_float(self):
        async with testutils.start_mockhost(
                script_root=self.durable_functions_dir) as host:

            func_id, r = await host.load_function(
                'activity_trigger_int_to_float')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'activity_trigger_int_to_float', [
                    # According to Durable Python
                    # Activity Trigger's input must be json serializable
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            json=str(int(10))
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(json='-11.0')
            )

    async def test_mock_orchestration_trigger(self):
        async with testutils.start_mockhost(
                script_root=self.durable_functions_dir) as host:

            func_id, r = await host.load_function('orchestration_trigger')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'orchestration_trigger', [
                    protos.ParameterBinding(
                        name='context',
                        data=protos.TypedData(
                            string='Durable functions coming soon'
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(json='Durable functions coming soon :)')
            )
