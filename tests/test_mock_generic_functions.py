from azure.functions_worker import protos
from azure.functions_worker import testutils


class TestGenericFunctions(testutils.AsyncTestCase):

    async def test_mock_generic_as_str(self):
        async with testutils.start_mockhost(
                script_root='generic_functions') as host:

            func_id, r = await host.load_function('foobar_as_str')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_as_str', [
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

    async def test_mock_generic_as_bytes(self):
        async with testutils.start_mockhost(
                script_root='generic_functions') as host:

            func_id, r = await host.load_function('foobar_as_bytes')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_as_bytes', [
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            bytes=b'\x00\x01'
                        )
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(bytes=b'\x00\x01')
            )
