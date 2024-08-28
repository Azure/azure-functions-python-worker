# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import pathlib
import time
from unittest import skipIf

from tests.utils import testutils
from tests.utils.constants import CONSUMPTION_DOCKER_TEST, DEDICATED_DOCKER_TEST

from azure_functions_worker.utils.common import is_envvar_true


class TestTableFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions'

    def test_table_bindings(self):
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)
        row_key = json.loads(out_resp.text)['RowKey']

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
        row_key_present = False
        for row in json.loads(in_resp.text):
            if row["RowKey"] == row_key:
                row_key_present = True
                break
        self.assertTrue(row_key_present)


class TestTableFunctionsStein(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions' / \
                                            'table_functions_stein'

    def test_table_bindings(self):
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)
        row_key = json.loads(out_resp.text)['RowKey']

        in_resp = self.webhost.request('GET', f'table_in_binding/{row_key}')
        self.assertEqual(in_resp.status_code, 200)
        row_key_present = False
        for row in json.loads(in_resp.text):
            if row["RowKey"] == row_key:
                row_key_present = True
                break
        self.assertTrue(row_key_present)


class TestTableFunctionsGeneric(TestTableFunctionsStein):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions' / \
                                            'table_functions_stein' /\
                                            'generic'
