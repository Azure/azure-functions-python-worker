# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time

from datetime import datetime
from dateutil import parser, tz

from azure_functions_worker import testutils
from azure_functions_worker.testutils import WebHostTestCase, E2E_TESTS_FOLDER


class TestKafkaFunctions(WebHostTestCase):
    """Test Kafka Trigger and Output Bindings (cardinality: one).

        Each testcase consists of 3 part:
        1. An Kafka_output HTTP trigger for generating Confluent/Eventhub event
        2. An actual kafka_trigger Confluent/EventHub trigger for storing event into blob
        3. A get_eventhub_triggered HTTP trigger for retrieving event eventhub info blob
        3. A get_confluent_triggered HTTP trigger for retrieving event confluent info blob
        """

    @classmethod
    def get_script_dir(cls):
        return E2E_TESTS_FOLDER / 'kafka_functions'

    @testutils.retryable_test(3, 5)
    def test_confluent_trigger(self):
        # Generate a unique event body for the kafka event
        data = str(round(time.time()))
        doc = 'test'

        # Invoke eventhub_output HttpTrigger to generate an kafka Event.
        r = self.webhost.request('POST', 'confluent_output', params={'message': doc})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, doc)

        # Once the event get generated, allow function host to pool from
        # EventHub and wait for eventhub_trigger to execute,
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_confluent_triggered to retrieve event metadata from blob.
        r = self.webhost.request('GET', 'confluent_get_metadata_triggered')
        self.assertEqual(r.status_code, 200)
        response = r.json()

        # Check if the event body matches the initial data
        self.assertEqual(response['Value'], doc)

    @testutils.retryable_test(3, 5)
    def test_kafka_confluent_trigger_with_metadata(self):
        # Generate a unique event body for EventHub event
        # Record the start_time and end_time for checking event enqueue time
        start_time = datetime.now(tz=tz.UTC)

        # Invoke metadata_output HttpTrigger to generate an EventHub event
        r = self.webhost.request('POST', 'confluent_metadata_output',
                                 params={'message' : 'test_meta'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('OK', r.text)
        end_time = datetime.now(tz=tz.UTC)

        # Once the event get generated, allow function host to pool from
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_metadata_triggered to retrieve event metadata from blob
        r = self.webhost.request('GET', 'confluent_get_metadata_triggered')
        self.assertEqual(r.status_code, 200)

        # Check if the event body matches the unique random_number
        event = r.json()

        self.assertIsNotNone(event['Partition'])
        self.assertIsNotNone(event['Offset'])
        self.assertGreaterEqual(event['Offset'], 0)
        self.assertEqual(event['Value'], 'test')
        self.assertEqual(event['Topic'], 'v4_test')
        enqueued_time = parser.isoparse(event['Timestamp'])
        self.assertTrue(start_time < enqueued_time < end_time)
