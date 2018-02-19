from azure.worker import protos
from azure.worker import testutils


class TestMockHost(testutils.AsyncTestCase):

    async def test_load_broken__missing_py_param(self):
        async with testutils.start_mockhost(
                script_root='broken_functions') as host:

            func_id, r = await host.load_function('missing_py_param')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

            self.assertRegex(
                r.response.result.exception.message,
                r".*cannot load the missing_py_param function"
                r".*parameters are declared in function.json"
                r".*'req'.*")

    async def test_load_broken__missing_json_param(self):
        async with testutils.start_mockhost(
                script_root='broken_functions') as host:

            func_id, r = await host.load_function('missing_json_param')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

            self.assertRegex(
                r.response.result.exception.message,
                r".*cannot load the missing_json_param function"
                r".*parameters are declared in Python"
                r".*'spam'.*")

    async def test_load_broken__wrong_param_dir(self):
        async with testutils.start_mockhost(
                script_root='broken_functions') as host:

            func_id, r = await host.load_function('wrong_param_dir')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

            self.assertRegex(
                r.response.result.exception.message,
                r'.*cannot load the wrong_param_dir function'
                r'.*binding foo is declared to have the "out".*')

    async def test_load_broken__wrong_binding_dir(self):
        async with testutils.start_mockhost(
                script_root='broken_functions') as host:

            func_id, r = await host.load_function('wrong_binding_dir')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

            self.assertRegex(
                r.response.result.exception.message,
                r'.*cannot load the wrong_binding_dir function'
                r'.* binding foo is declared to have the "in" direction'
                r'.*but its annotation is.*Out.*')

    async def test_load_broken__invalid_context_param(self):
        async with testutils.start_mockhost(
                script_root='broken_functions') as host:

            func_id, r = await host.load_function('invalid_context_param')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

            self.assertRegex(
                r.response.result.exception.message,
                r'.*cannot load the invalid_context_param function'
                r'.*the "context" parameter.*')

    async def test_load_broken__syntax_error(self):
        async with testutils.start_mockhost(
                script_root='broken_functions') as host:

            func_id, r = await host.load_function('syntax_error')

            self.assertEqual(r.response.function_id, func_id)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Failure)

            self.assertIn('SyntaxError', r.response.result.exception.message)
