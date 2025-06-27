# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from tests.utils import testutils

class TestServiceBusBatchFunctionsStein(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'servicebus_batch_functions' / \
            'servicebus_batch_functions_stein'

    @testutils.retryable_test(3, 5)
    def test_servicebus_multiple(self):
        NUM_EVENTS = 3
        all_row_keys_seen = dict([(i, True) for i in range(NUM_EVENTS)])
        partition_key = str(round(time.time()))

        docs = []
        for i in range(NUM_EVENTS):
            doc = {'PartitionKey': partition_key, 'RowKey': i}
            docs.append(doc)

        r = self.webhost.request('POST', 'servicebus_output_batch',
                                 data=json.dumps(docs))
        self.assertEqual(r.status_code, 200)

        row_keys = [i for i in range(NUM_EVENTS)]
        seen = [False] * NUM_EVENTS
        row_keys_seen = dict(zip(row_keys, seen))

        # Allow trigger to fire.
        time.sleep(5)

        r = self.webhost.request(
            'GET',
            'get_servicebus_batch_triggered')
        self.assertEqual(r.status_code, 200)
        entries = r.json()
        for entry in entries:
            self.assertEqual(entry['PartitionKey'], partition_key)
            row_key = entry['RowKey']
            row_keys_seen[row_key] = True

        self.assertDictEqual(all_row_keys_seen, row_keys_seen)
