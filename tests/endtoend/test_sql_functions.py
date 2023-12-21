# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import os
from unittest import skip
from unittest.mock import patch

from tests.utils import testutils


@skip("Unskip when azure functions with SQL is released.")
class TestSqlFunctions(testutils.WebHostTestCase):

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
