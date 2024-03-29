# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from azure_functions_worker import protos
from tests.utils import testutils


class TestGenericFunctions(testutils.AsyncTestCase):
    generic_funcs_dir = testutils.UNIT_TESTS_FOLDER / 'generic_functions'

    async def test_mock_generic_as_str(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
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
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
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

    async def test_mock_generic_as_str_no_anno(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('foobar_as_str_no_anno')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_as_str_no_anno', [
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

    async def test_mock_generic_as_bytes_no_anno(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('foobar_as_bytes_no_anno')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_as_bytes_no_anno', [
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

    async def test_mock_generic_should_support_implicit_output(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('foobar_implicit_output')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_implicit_output', [
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            bytes=b'\x00\x01'
                        )
                    )
                ]
            )
            # It passes now as we are enabling generic binding to return output
            # implicitly
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(bytes=b'\x00\x01'))

    async def test_mock_generic_should_support_without_datatype(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('foobar_with_no_datatype')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_with_no_datatype', [
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            bytes=b'\x00\x01'
                        )
                    )
                ]
            )
            # It passes now as we are enabling generic binding to return output
            # implicitly
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

    async def test_mock_generic_implicit_output_exemption(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:
            await host.init_worker("4.17.1")
            func_id, r = await host.load_function(
                'foobar_implicit_output_exemption')
            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_implicit_output_exemption', [
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData(
                            bytes=b'\x00\x01'
                        )
                    )
                ]
            )
            # It should fail here, since implicit output is False
            # For the Durable Functions durableClient case
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

    async def test_mock_generic_as_nil_data(self):
        async with testutils.start_mockhost(
                script_root=self.generic_funcs_dir) as host:

            await host.init_worker("4.17.1")
            func_id, r = await host.load_function('foobar_nil_data')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)

            _, r = await host.invoke_function(
                'foobar_nil_data', [
                    protos.ParameterBinding(
                        name='input',
                        data=protos.TypedData()
                    )
                ]
            )
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertEqual(
                r.response.return_value,
                protos.TypedData(string="This is fine"))
