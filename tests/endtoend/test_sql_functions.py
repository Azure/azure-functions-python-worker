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
    def test_sql_output_and_input(self):
        row = {"ProductId": 0, "Name": "test", "Cost": 100}
        r = self.webhost.request('POST', 'sql_output',
                                 data=json.dumps(row))
        self.assertEqual(r.status_code, 201)

        r = self.webhost.request('GET', 'sql_input')
        self.assertEqual(r.status_code, 200)
        expectedText = "[{\"ProductId\": 0, \"Name\": \"test\", \"Cost\": 100}]"
        self.assertEqual(r.text, expectedText)

    @testutils.retryable_test(1, 5)
    def test_sql_trigger(self):
        time.sleep(5)
        id = str(round(time.time()))
        row = {"ProductId": id, "Name": "test", "Cost": 100}
        r = self.webhost.request('POST', 'sql_output',
                                 data=json.dumps(row))
        self.assertEqual(r.status_code, 201)

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire
            time.sleep(2)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_sql_triggered')
                self.assertEqual(r.status_code, 200)
                actualText = ''.join(r.text.split())
                expectedText = "[{\"Operation\":0,\"Item\":{\"ProductId\":" + id + \
                    ",\"Name\":\"test\",\"Cost\":100}}]"
                self.assertEqual(actualText, expectedText)

            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break


class TestSqlFunctionsStein(TestSqlFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'sql_functions' / \
            'sql_functions_stein'


class TestSqlFunctionsSteinGeneric(TestSqlFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'sql_functions' / \
            'sql_functions_stein' / 'generic'
