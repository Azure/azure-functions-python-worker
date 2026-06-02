# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from tests.utils import testutils
from unittest import skipIf
import sys


class TestEventHubFunctions(testutils.WebHostTestCase):
    """Test EventHub Trigger and Output Bindings (cardinality: one).

    Each testcase consists of 3 part:
    1. An eventhub_output HTTP trigger for generating EventHub event
    2. An actual eventhub_trigger EventHub trigger for storing event into blob
    3. A get_eventhub_triggered HTTP trigger for retrieving event info blob
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventhub_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-eventhub']

    @testutils.retryable_test(3, 5)
    def test_eventhub_trigger(self):
        # Generate a unique event body for the EventHub event
        data = str(round(time.time()))
        doc = {'id': data}

        # Invoke eventhub_output HttpTrigger to generate an Eventhub Event.
        r = self.webhost.request('POST', 'eventhub_output',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Once the event get generated, allow function host to poll from
        # EventHub and wait for eventhub_trigger to execute,
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_eventhub_triggered to retrieve event metadata from blob.
        r = self.webhost.request('GET', 'get_eventhub_triggered')

        # Waiting for the blob get updated with the latest data from the
        # eventhub output binding
        time.sleep(5)
        self.assertEqual(r.status_code, 200)
        response = r.json()

        # Check if the event body matches the initial data
        self.assertEqual(response, doc)

    @testutils.retryable_test(3, 5)
    def test_eventhub_trigger_with_metadata(self):
        # Generate a unique event body for EventHub event
        # Record the start_time and end_time for checking event enqueue time
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }

        # Invoke metadata_output HttpTrigger to generate an EventHub event
        # from azure-eventhub SDK
        r = self.webhost.request('POST', 'metadata_output',
                                 data=json.dumps(req_body))
        self.assertEqual(r.status_code, 200)
        self.assertIn('OK', r.text)

        # Once the event get generated, allow function host to pool from
        # EventHub and wait for eventhub_trigger to execute,
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_metadata_triggered to retrieve event metadata from blob
        r = self.webhost.request('GET', 'get_metadata_triggered')

        # Waiting for the blob get updated with the latest data from the
        # eventhub output binding
        time.sleep(5)
        self.assertEqual(r.status_code, 200)

        # Check if the event body matches the unique random_number
        event = r.json()
        self.assertEqual(event['body'], random_number)

        # EventhubEvent property check
        # Reenable these lines after enqueued_time property is fixed
        # enqueued_time = parser.isoparse(event['enqueued_time'])
        # self.assertIsNotNone(enqueued_time)
        self.assertIsNone(event['partition_key'])  # There's only 1 partition
        self.assertGreaterEqual(event['sequence_number'], 0)
        self.assertIsNotNone(event['offset'])

        # Check if the event contains proper metadata fields
        self.assertIsNotNone(event['metadata'])
        metadata = event['metadata']
        sys_props = metadata['SystemProperties']
        self.assertIsNone(sys_props['PartitionKey'])
        self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
        self.assertIsNotNone(sys_props['Offset'])


class TestEventHubFunctionsStein(TestEventHubFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventhub_functions' / \
            'eventhub_functions_stein'


class TestEventHubFunctionsSteinGeneric(TestEventHubFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventhub_functions' / \
            'eventhub_functions_stein' / 'generic'


class TestEventHubRetryStein(testutils.WebHostTestCase):
    """Test EventHub Trigger with Retry Policy"""

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / \
            'eventhub_functions' / 'eventhub_retry_stein'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-eventhub']

    @testutils.retryable_test(3, 5)
    def test_eventhub_retry_trigger_with_default_intervals(self):
        """Test that exponential backoff retry works with default intervals."""
        # Generate a unique event ID
        event_id = f"retry-test-{round(time.time())}"
        doc = {'id': event_id}

        # Reset retry state
        r = self.webhost.request('POST', 'reset_retry_state')
        self.assertEqual(r.status_code, 200)

        # Send event to EventHub
        r = self.webhost.request(
            'POST', 'eventhub_retry_output', data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Wait for retries to complete (with exponential backoff)
        # First attempt: immediate
        # Second attempt: after backoff
        # Third attempt: after longer backoff
        time.sleep(15)

        # Retrieve the result from blob storage
        r = self.webhost.request('GET', 'get_eventhub_retry_triggered')
        self.assertEqual(r.status_code, 200)

        result = json.loads(r.text)

        # Verify the event was processed after retries
        self.assertIn(event_id, result['event_id'])
        # Should succeed on third attempt (count 2)
        self.assertEqual(result['retry_count'], 2)
        self.assertEqual(result['max_retry_count'], 3)

        # Verify all retry attempts were tracked
        self.assertEqual(len(result['all_attempts']), 3)  # 0, 1, 2
        self.assertEqual(result['all_attempts'], [0, 1, 2])


@skipIf(sys.version_info.minor >= 14, "Skip to figure out uamqp.")
class TestEventHubFunctionsSDK(TestEventHubFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventhub_functions' / \
            'eventhub_functions_sdk'
