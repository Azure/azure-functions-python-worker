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
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            string='test'
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string='test')
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
                protos.TypedData(string='Durable functions coming soon :)')
            )
