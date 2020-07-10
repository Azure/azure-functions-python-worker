# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time
import pathlib
from datetime import datetime

from azure_functions_worker import testutils


class TestEventHubFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'eventhub_batch_functions'

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple(self):
        NUM_EVENTS = 3
        all_row_keys_seen = dict([(str(i), True) for i in range(NUM_EVENTS)])
        partition_key = str(round(time.time()))

        # Dynamically rewrite function.json to point to new partition key
        # for recording EventHub state
        old_partition_key = self._get_table_partition_key()
        self._set_table_partition_key(partition_key)

        # wait for host to restart after change
        time.sleep(5)

        docs = []
        for i in range(NUM_EVENTS):
            doc = {'PartitionKey': partition_key, 'RowKey': i}
            docs.append(doc)

        r = self.webhost.request('POST', 'eventhub_output_batch',
                                 data=json.dumps(docs))
        self.assertEqual(r.status_code, 200)

        row_keys = [str(i) for i in range(NUM_EVENTS)]
        seen = [False] * NUM_EVENTS
        row_keys_seen = dict(zip(row_keys, seen))

        # Allow trigger to fire.
        time.sleep(5)

        try:
            r = self.webhost.request('GET', 'get_eventhub_batch_triggered')
            self.assertEqual(r.status_code, 200)
            entries = r.json()
            for entry in entries:
                self.assertEqual(entry['PartitionKey'], partition_key)
                row_key = entry['RowKey']
                row_keys_seen[row_key] = True

            self.assertDictEqual(all_row_keys_seen, row_keys_seen)
        finally:
            self._cleanup(old_partition_key)

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple_with_metadata(self):
        # Send a eventhub event with a random_number in the body
        start_time = datetime.utcnow()
        count = 10
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }
        r = self.webhost.request('POST',
                                 f'metadata_output_batch?count={count}',
                                 data=json.dumps(req_body))
        self.assertEqual(r.status_code, 200)
        self.assertIn('OK', r.text)
        end_time = datetime.utcnow()

        # Allow trigger to fire.
        time.sleep(5)

        # Check that the trigger has fired.
        r = self.webhost.request('GET', 'get_metadata_batch_triggered')
        self.assertEqual(r.status_code, 200)

        # Check metadata and events length, events should be batch processed
        events = r.json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 1)

        # EventhubEvent property check
        # Reenable these lines after enqueued_time property is fixed
        for event in events:
            event_index = int(event['body']) - int(random_number)
            self.assertTrue(0 <= event_index < count)

            enqueued_time = datetime.fromisoformat(event['enqueued_time'])
            self.assertIsNotNone(enqueued_time)
            self.assertIsNone(event['partition_key'])  # only 1 partition
            self.assertGreaterEqual(event['sequence_number'], 0)
            self.assertIsNotNone(event['offset'])

            # Metadata check essential properties
            self.assertIsNotNone(event['metadata'])
            metadata = event['metadata']
            sys_props_array = metadata['SystemPropertiesArray']
            sys_props = sys_props_array[event_index]
            enqueued_time = datetime.strptime(sys_props['EnqueuedTimeUtc'],
                                              '%Y-%m-%dT%H:%M:%S.%fZ')

            # Check event trigger time and other system properties
            self.assertTrue(start_time < enqueued_time < end_time)
            self.assertIsNone(sys_props['PartitionKey'])
            self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
            self.assertIsNotNone(sys_props['Offset'])

            # Metadata check eventhub trigger name
            self.assertEqual(metadata['sys']['MethodName'],
                             'metadata_multiple')

    def _cleanup(self, old_partition_key):
        self._set_table_partition_key(old_partition_key)

    def _get_table_partition_key(self):
        func_dict = self._get_table_function_json_dict()
        partition_key = func_dict['bindings'][1]['partitionKey']
        return partition_key

    def _set_table_partition_key(self, partition_key):
        full_json_path = self._get_table_function_json_path()

        func_dict = self._get_table_function_json_dict()
        func_dict['bindings'][1]['partitionKey'] = partition_key

        with open(full_json_path, 'w') as f:
            json.dump(func_dict, f, indent=2)

    def _get_table_function_json_dict(self):
        full_json_path = self._get_table_function_json_path()

        with open(full_json_path, 'r') as f:
            func_dict = json.load(f)

        return func_dict

    def _get_table_function_json_path(self):
        script_dir = pathlib.Path(self.get_script_dir())
        json_path = pathlib.Path('get_eventhub_batch_triggered/function.json')
        return testutils.TESTS_ROOT / script_dir / json_path
