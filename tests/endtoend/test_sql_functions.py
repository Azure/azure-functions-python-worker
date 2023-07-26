# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time
from unittest import skip

from tests.utils import testutils


class TestSqlFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'sql_functions'

    @testutils.retryable_test(3, 5)
    def test_sql_output_and_input(self):
        name = str(round(time.time()))
        row = {"ProductId": 1, "Name": name, "Cost": 100}
        r = self.webhost.request('POST', 'sql_output',
                                 data=json.dumps(row))
        self.assertEqual(r.status_code, 201)

        r = self.webhost.request('GET', 'sql_input')
        self.assertEqual(r.status_code, 200)
        expectedText = "[{\"ProductId\": 1, \"Name\": \"" + name + "\", \"Cost\": 100}]"
        self.assertEqual(r.text, expectedText)


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
