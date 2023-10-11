# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from tests.utils import testutils


class TestSqlFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'sql_functions'

    @testutils.retryable_test(3, 5)
    def test_sql_binding_trigger(self):
        id = str(round(time.time()))
        row = {"ProductId": id, "Name": "test", "Cost": 100}
        # Insert a row into Products table using sql_output function
        r = self.webhost.request('POST', 'sql_output',
                                 data=json.dumps(row))
        self.assertEqual(r.status_code, 201)

        # Check that the row was successfully inserted using sql_input function
        r = self.webhost.request('GET', 'sql_input/' + id)
        self.assertEqual(r.status_code, 200)
        expectedText = "[{\"ProductId\": " + id + \
            ", \"Name\": \"test\", \"Cost\": 100}]"
        self.assertEqual(r.text, expectedText)

        # Check that the sql_trigger function has been triggered and
        # the row has been inserted into Products2 table using sql_input2 function
        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire
            time.sleep(2)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'sql_input2/' + id)
                self.assertEqual(r.status_code, 200)
                expectedText = "[{\"ProductId\": " + id + \
                    ", \"Name\": \"test\", \"Cost\": 100}]"
                self.assertEqual(r.text, expectedText)

            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break
