# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import pathlib
import time

from azure_functions_worker import testutils


class TestTableFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'table_functions'

    @testutils.retryable_test(3, 5)
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
