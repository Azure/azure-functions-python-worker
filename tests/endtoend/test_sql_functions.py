# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from azure_functions_worker import testutils


class TestSqlFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'sql_functions'

    @testutils.retryable_test(3, 5)
    def test_sql_output_and_input(self):
        time.sleep(5)
        row = {'id': '1', 'name': 'test', 'cost': 100}
        r = self.webhost.request('POST', 'add_product',
                                 data=json.dumps(row))
        self.assertEqual(r.status_code, 201)

        max_retries = 10

        for try_no in range(max_retries):
            try:
                r = self.webhost.request('GET', 'get_product')
                self.assertEqual(r.status_code, 201)
                response = r.json()

                self.assertEqual(
                    response,
                    row
                )
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break
