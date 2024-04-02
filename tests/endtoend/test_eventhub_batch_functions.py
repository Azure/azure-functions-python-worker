# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time
from datetime import datetime
from unittest import skipIf

from dateutil import parser, tz

from azure_functions_worker.utils.common import is_envvar_true
from tests.utils import testutils
from tests.utils.constants import DEDICATED_DOCKER_TEST, CONSUMPTION_DOCKER_TEST


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Table functions which are used in the bindings in these tests"
        " has a bug with the table extension 1.0.0. "
        "https://github.com/Azure/azure-sdk-for-net/issues/33902.")
class TestEventHubFunctions(testutils.WebHostTestCase):
    """Test EventHub Trigger and Output Bindings (cardinality: many).

    Each testcase consists of 3 part:
    1. An eventhub_output_batch HTTP trigger for generating EventHub event
    2. An eventhub_multiple EventHub trigger for converting event into blob
    3. A get_eventhub_batch_triggered HTTP trigger for the event body
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'eventhub_batch_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-eventhub']

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple(self):
        NUM_EVENTS = 3
        all_row_keys_seen = dict([(i, True) for i in range(NUM_EVENTS)])
        partition_key = str(round(time.time()))

        # wait for host to restart after change
        time.sleep(5)

        docs = []
        for i in range(NUM_EVENTS):
            doc = {'PartitionKey': partition_key, 'RowKey': i}
            docs.append(doc)

        r = self.webhost.request('POST', 'eventhub_output_batch',
                                 data=json.dumps(docs))
        self.assertEqual(r.status_code, 200)

        row_keys = [i for i in range(NUM_EVENTS)]
        seen = [False] * NUM_EVENTS
        row_keys_seen = dict(zip(row_keys, seen))

        # Allow trigger to fire.
        time.sleep(5)

        r = self.webhost.request('GET', 'get_eventhub_batch_triggered')

        # Waiting for the blob get updated with the latest data from the
        # eventhub output binding
        time.sleep(2)
        self.assertEqual(r.status_code, 200)
        entries = r.json()
        for entry in entries:
            self.assertEqual(entry['PartitionKey'], partition_key)
            row_key = entry['RowKey']
            row_keys_seen[row_key] = True

        self.assertDictEqual(all_row_keys_seen, row_keys_seen)

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple_with_metadata(self):
        # Generate a unique event body for EventHub event
        # Record the start_time and end_time for checking event enqueue time
        start_time = datetime.utcnow()
        count = 10
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }

        # Invoke metadata_output HttpTrigger to generate an EventHub event
        # from azure-eventhub SDK
        r = self.webhost.request('POST',
                                 f'metadata_output_batch?count={count}',
                                 data=json.dumps(req_body))
        self.assertEqual(r.status_code, 200)
        self.assertIn('OK', r.text)
        end_time = datetime.utcnow()

        # Once the event get generated, allow function host to pool from
        # EventHub and wait for metadata_multiple to execute,
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_metadata_batch_triggered to retrieve event metadata
        r = self.webhost.request('GET', 'get_metadata_batch_triggered')
        self.assertEqual(r.status_code, 200)

        # Check metadata and events length, events should be batched processed
        events = r.json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 1)

        # EventhubEvent property check
        for event_index in range(len(events)):
            event = events[event_index]

            # Check if the event is enqueued between start_time and end_time
            enqueued_time = parser.isoparse(event['enqueued_time'])
            self.assertTrue(start_time < enqueued_time < end_time)

            # Check if event properties are properly set
            self.assertIsNone(event['partition_key'])  # only 1 partition
            self.assertGreaterEqual(event['sequence_number'], 0)
            self.assertIsNotNone(event['offset'])

            # Check if event.metadata field is properly set
            self.assertIsNotNone(event['metadata'])
            metadata = event['metadata']
            sys_props_array = metadata['SystemPropertiesArray']
            sys_props = sys_props_array[event_index]
            enqueued_time = parser.isoparse(sys_props['EnqueuedTimeUtc'])

            # Check event trigger time and other system properties
            self.assertTrue(
                start_time.timestamp() < enqueued_time.timestamp() < end_time.timestamp())  # NoQA
            self.assertIsNone(sys_props['PartitionKey'])
            self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
            self.assertIsNotNone(sys_props['Offset'])


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Table functions which are used in the bindings has a bug with the"
        " table extension 1.0.0. "
        "https://github.com/Azure/azure-sdk-for-net/issues/33902.")
class TestEventHubBatchFunctionsStein(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'eventhub_batch_functions' / \
            'eventhub_batch_functions_stein'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-eventhub']

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple(self):
        NUM_EVENTS = 3
        all_row_keys_seen = dict([(i, True) for i in range(NUM_EVENTS)])
        partition_key = str(round(time.time()))

        docs = []
        for i in range(NUM_EVENTS):
            doc = {'PartitionKey': partition_key, 'RowKey': i}
            docs.append(doc)

        r = self.webhost.request('POST', 'eventhub_output_batch',
                                 data=json.dumps(docs))
        self.assertEqual(r.status_code, 200)

        row_keys = [i for i in range(NUM_EVENTS)]
        seen = [False] * NUM_EVENTS
        row_keys_seen = dict(zip(row_keys, seen))

        # Allow trigger to fire.
        time.sleep(5)

        r = self.webhost.request(
            'GET',
            'get_eventhub_batch_triggered')
        self.assertEqual(r.status_code, 200)
        entries = r.json()
        for entry in entries:
            self.assertEqual(entry['PartitionKey'], partition_key)
            row_key = entry['RowKey']
            row_keys_seen[row_key] = True

        self.assertDictEqual(all_row_keys_seen, row_keys_seen)

    @testutils.retryable_test(3, 5)
    def test_eventhub_multiple_with_metadata(self):
        # Generate a unique event body for EventHub event
        # Record the start_time and end_time for checking event enqueue time
        start_time = datetime.utcnow()
        count = 10
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }

        # Invoke metadata_output HttpTrigger to generate an EventHub event
        # from azure-eventhub SDK
        r = self.webhost.request('POST',
                                 f'metadata_output_batch?count={count}',
                                 data=json.dumps(req_body))
        self.assertEqual(r.status_code, 200)
        self.assertIn('OK', r.text)
        end_time = datetime.utcnow()

        # Once the event get generated, allow function host to pool from
        # EventHub and wait for metadata_multiple to execute,
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_metadata_batch_triggered to retrieve event metadata
        r = self.webhost.request('GET', 'get_metadata_batch_triggered')
        self.assertEqual(r.status_code, 200)

        # Check metadata and events length, events should be batched processed
        events = r.json()
        self.assertIsInstance(events, list)
        self.assertGreater(len(events), 1)

        # EventhubEvent property check
        for event_index in range(len(events)):
            event = events[event_index]

            # Check if the event is enqueued between start_time and end_time
            enqueued_time = parser.isoparse(event['enqueued_time'])
            self.assertTrue(start_time < enqueued_time < end_time)

            # Check if event properties are properly set
            self.assertIsNone(event['partition_key'])  # only 1 partition
            self.assertGreaterEqual(event['sequence_number'], 0)
            self.assertIsNotNone(event['offset'])

            # Check if event.metadata field is properly set
            self.assertIsNotNone(event['metadata'])
            metadata = event['metadata']
            sys_props_array = metadata['SystemPropertiesArray']
            sys_props = sys_props_array[event_index]
            enqueued_time = parser.isoparse(sys_props['EnqueuedTimeUtc'])

            # Check event trigger time and other system properties
            self.assertTrue(
                start_time.timestamp() < enqueued_time.timestamp()
                < end_time.timestamp())  # NoQA
            self.assertIsNone(sys_props['PartitionKey'])
            self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
            self.assertIsNotNone(sys_props['Offset'])
