# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time
from datetime import datetime

from azure_functions_worker import testutils


class TestEventHubFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'eventhub_functions'

    @testutils.retryable_test(3, 5)
    def test_eventhub_trigger(self):
        data = str(round(time.time()))
        doc = {'id': data}
        r = self.webhost.request('POST', 'eventhub_output',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Allow trigger to fire.
        time.sleep(5)

        # Check that the trigger has fired.
        r = self.webhost.request('GET', 'get_eventhub_triggered')
        self.assertEqual(r.status_code, 200)
        response = r.json()

        self.assertEqual(response, doc)

    @testutils.retryable_test(3, 5)
    def test_eventhub_trigger_with_metadata(self):
        # Send a eventhub event with a random_number in the body
        start_time = datetime.utcnow()
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }
        r = self.webhost.request('POST', 'metadata_output',
                                 data=json.dumps(req_body))
        self.assertEqual(r.status_code, 200)
        self.assertIn('OK', r.text)
        end_time = datetime.utcnow()

        # Allow trigger to fire.
        time.sleep(5)

        # Check that the trigger has fired.
        r = self.webhost.request('GET', 'get_metadata_triggered')
        self.assertEqual(r.status_code, 200)

        # Check metadata
        event = r.json()
        self.assertEqual(event['body'], random_number)

        # EventhubEvent property check
        # Reenable these lines after enqueue_time property is fixed
        # enqueue_time = datetime.fromisoformat(event['enqueue_time'])
        # self.assertTrue(start_time < enqueue_time < end_time)
        self.assertIsNone(event['partition_key'])  # There's only 1 partition
        self.assertGreaterEqual(event['sequence_number'], 0)
        self.assertIsNotNone(event['offset'])

        # Metadata check essential properties
        self.assertIsNotNone(event['metadata'])
        metadata = event['metadata']
        sys_props = metadata['SystemProperties']
        enqueue_time = datetime.strptime(metadata['EnqueuedTimeUtc'],
                                         '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertTrue(start_time < enqueue_time < end_time)
        self.assertIsNone(sys_props['PartitionKey'])
        self.assertGreaterEqual(sys_props['SequenceNumber'], 0)
        self.assertIsNotNone(sys_props['Offset'])

        # Metadata check eventhub trigger name
        self.assertEqual(metadata['sys']['MethodName'], 'metadata_trigger')
