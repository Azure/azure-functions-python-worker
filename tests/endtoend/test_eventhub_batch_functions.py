import json
import time
import pathlib

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
