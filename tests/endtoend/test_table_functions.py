# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import pathlib
import os
import time
from unittest import skipIf
from unittest.mock import patch

from azure_functions_worker.utils.common import is_envvar_true
from tests.utils import testutils
from tests.utils.constants import DEDICATED_DOCKER_TEST, \
    CONSUMPTION_DOCKER_TEST


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Table functions has a bug with the table extension 1.0.0."
        "https://github.com/Azure/azure-sdk-for-net/issues/33902.")
class TestTableFunctions(testutils.WebHostTestCase):

    @classmethod
    def setUpClass(cls):
        cls.env_variables['PYTHON_SCRIPT_FILE_NAME'] = 'function_app.py'

        os_environ = os.environ.copy()
        os_environ.update(cls.env_variables)

        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions'

    def test_table_bindings(self):
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)
        row_key = out_resp.headers['rowKey']

        script_dir = pathlib.Path(self.get_script_dir())
        json_path = pathlib.Path('table_in_binding/function.json')
        full_json_path = testutils.TESTS_ROOT / script_dir / json_path
        # Dynamically rewrite function.json to point to new row key
        with open(full_json_path, 'r') as f:
            func_dict = json.load(f)
            func_dict['bindings'][1]['rowKey'] = row_key

        with open(full_json_path, 'w') as f:
            json.dump(func_dict, f, indent=2)

        # wait for host to restart after change
        time.sleep(1)

        in_resp = self.webhost.request('GET', 'table_in_binding')
        self.assertEqual(in_resp.status_code, 200)
        in_row_key = in_resp.headers['rowKey']
        self.assertEqual(in_row_key, row_key)


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Table functions has a bug with the table extension 1.0.0."
        "https://github.com/Azure/azure-sdk-for-net/issues/33902.")
class TestTableFunctionsStein(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions' / \
                                            'table_functions_stein'

    def test_table_bindings(self):
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)
        row_key = out_resp.headers['rowKey']

        in_resp = self.webhost.request('GET', f'table_in_binding/{row_key}')
        self.assertEqual(in_resp.status_code, 200)
        in_row_key = in_resp.headers['rowKey']
        self.assertEqual(in_row_key, row_key)


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Table functions has a bug with the table extension 1.0.0."
        "https://github.com/Azure/azure-sdk-for-net/issues/33902.")
class TestTableFunctionsGeneric(TestTableFunctionsStein):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions' / \
                                            'table_functions_stein' /\
                                            'generic'
