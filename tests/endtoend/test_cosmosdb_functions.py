# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from azure_functions_worker import testutils


class TestCosmosDBFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'cosmosdb_functions'

    @testutils.retryable_test(3, 5)
    def test_cosmosdb_trigger(self):
        time.sleep(5)
        data = str(round(time.time()))
        doc = {'id': 'cosmosdb-trigger-test', 'data': data}
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire
            time.sleep(2)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_cosmosdb_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()
                response.pop('_metadata', None)

                self.assertEqual(
                    response,
                    doc
                )
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break

    @testutils.retryable_test(3, 5)
    def test_cosmosdb_input(self):
        time.sleep(5)
        data = str(round(time.time()))
        doc = {'id': 'cosmosdb-input-test', 'data': data}
        r = self.webhost.request('POST', 'put_document',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire
            time.sleep(2)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'cosmosdb_input')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(
                    response,
                    doc
                )
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break
