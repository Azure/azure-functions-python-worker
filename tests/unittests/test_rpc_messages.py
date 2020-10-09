# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import subprocess
import sys
import tempfile
import typing
import unittest

from azure_functions_worker import protos
from azure_functions_worker import testutils


class TestGRPC(testutils.AsyncTestCase):
    pre_test_env = os.environ.copy()
    pre_test_cwd = os.getcwd()

    def _reset_environ(self):
        for key, value in self.pre_test_env.items():
            os.environ[key] = value
        os.chdir(self.pre_test_cwd)

    async def _verify_environment_reloaded(
            self,
            test_env: typing.Dict[str, str] = {},
            test_cwd: str = os.getcwd()):
        request = protos.FunctionEnvironmentReloadRequest(
            environment_variables=test_env,
            function_app_directory=test_cwd)

        request_msg = protos.StreamingMessage(
            request_id='0',
            function_environment_reload_request=request)

        disp = testutils.create_dummy_dispatcher()

        try:
            r = await disp._handle__function_environment_reload_request(
                request_msg)

            environ_dict = os.environ.copy()
            self.assertDictEqual(environ_dict, test_env)
            self.assertEqual(os.getcwd(), test_cwd)
            status = r.function_environment_reload_response.result.status
            self.assertEqual(status, protos.StatusResult.Success)
        finally:
            self._reset_environ()

    async def test_multiple_env_vars_load(self):
        test_env = {'TEST_KEY': 'foo', 'HELLO': 'world'}
        await self._verify_environment_reloaded(test_env=test_env)

    async def test_empty_env_vars_load(self):
        test_env = {}
        await self._verify_environment_reloaded(test_env=test_env)

    @unittest.skipIf(sys.platform == 'darwin',
                     'MacOS creates the processes specific var folder in '
                     '/private filesystem and not in /var like in linux '
                     'systems.')
    async def test_changing_current_working_directory(self):
        test_cwd = tempfile.gettempdir()
        await self._verify_environment_reloaded(test_cwd=test_cwd)

    @unittest.skipIf(sys.platform == 'darwin',
                     'MacOS creates the processes specific var folder in '
                     '/private filesystem and not in /var like in linux '
                     'systems.')
    async def test_reload_env_message(self):
        test_env = {'TEST_KEY': 'foo', 'HELLO': 'world'}
        test_cwd = tempfile.gettempdir()
        await self._verify_environment_reloaded(test_env, test_cwd)

    def _verify_sys_path_import(self, result, expected_output):
        path_import_script = os.path.join(testutils.UNIT_TESTS_ROOT,
                                          'path_import', 'test_path_import.sh')
        try:
            subprocess.run(['chmod +x ' + path_import_script], shell=True)

            exported_path = ":".join(sys.path)
            output = subprocess.check_output(
                [path_import_script, result, exported_path],
                stderr=subprocess.STDOUT)
            decoded_output = output.decode(sys.stdout.encoding).strip()
            self.assertTrue(expected_output in decoded_output)
        finally:
            subprocess.run(['chmod -x ' + path_import_script], shell=True)
            self._reset_environ()

    @unittest.skipIf(sys.platform == 'win32',
                     'Linux .sh script only works on Linux')
    def test_failed_sys_path_import(self):
        self._verify_sys_path_import(
            'fail',
            "No module named 'test_module'")

    @unittest.skipIf(sys.platform == 'win32',
                     'Linux .sh script only works on Linux')
    def test_successful_sys_path_import(self):
        self._verify_sys_path_import(
            'success',
            'This module was imported!')

    def _verify_azure_namespace_import(self, result, expected_output):
        print(os.getcwd())
        path_import_script = os.path.join(testutils.UNIT_TESTS_ROOT,
                                          'azure_namespace_import',
                                          'test_azure_namespace_import.sh')
        try:
            subprocess.run(['chmod +x ' + path_import_script], shell=True)

            output = subprocess.check_output(
                [path_import_script, result],
                stderr=subprocess.STDOUT)
            decoded_output = output.decode(sys.stdout.encoding).strip()
            self.assertTrue(expected_output in decoded_output)
        finally:
            subprocess.run(['chmod -x ' + path_import_script], shell=True)
            self._reset_environ()

    @unittest.skipIf(sys.platform == 'win32',
                     'Linux .sh script only works on Linux')
    def test_failed_azure_namespace_import(self):
        self._verify_azure_namespace_import(
            'false',
            'module_b fails to import')

    @unittest.skipIf(sys.platform == 'win32',
                     'Linux .sh script only works on Linux')
    def test_successful_azure_namespace_import(self):
        self._verify_azure_namespace_import(
            'true',
            'module_b is imported')
