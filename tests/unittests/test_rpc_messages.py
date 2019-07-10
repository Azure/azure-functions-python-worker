import os
import subprocess
import sys

from azure.functions_worker import protos
from azure.functions_worker import testutils


class TestGRPC(testutils.AsyncTestCase):
    pre_test_env = os.environ.copy()

    def _reset_environ(self):
        for key, value in self.pre_test_env.items():
            os.environ[key] = value

    async def _verify_environment_reloaded(self, test_env):
            request = protos.FunctionEnvironmentReloadRequest(
                environment_variables=test_env)

            request_msg = protos.StreamingMessage(
                request_id='0',
                function_environment_reload_request=request)

            disp = testutils.create_dummy_dispatcher()

            try:
                r = await disp._handle__function_environment_reload_request(
                    request_msg)

                environ_dict = os.environ.copy()
                self.assertDictEqual(environ_dict, test_env)
                status = r.function_environment_reload_response.result.status
                self.assertEqual(status, protos.StatusResult.Success)
            finally:
                self._reset_environ()

    async def test_multiple_env_vars_load(self):
        test_env = {'TEST_KEY': 'foo', 'HELLO': 'world'}
        await self._verify_environment_reloaded(test_env)

    async def test_empty_env_vars_load(self):
        test_env = {}
        await self._verify_environment_reloaded(test_env)

    def _verify_sys_path_import(self, result, expected_output):
        try:
            path_import_script = os.path.join(
                testutils.UNIT_TESTS_ROOT,
                'path_import',
                'test_path_import.sh')

            subprocess.run(['chmod +x ' + path_import_script], shell=True)

            exported_path = ":".join(sys.path)
            output = subprocess.check_output(
                [path_import_script, result, exported_path],
                stderr=subprocess.STDOUT)
            decoded_output = output.decode(sys.stdout.encoding).strip()
            self.assertTrue(expected_output in decoded_output)
        finally:
            self._reset_environ()

    def test_failed_sys_path_import(self):
        self._verify_sys_path_import(
            'fail',
            "No module named 'test_module'")

    def test_successful_sys_path_import(self):
        self._verify_sys_path_import(
            'success',
            'This module was imported!')
