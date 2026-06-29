# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import sys
import time
import unittest

from tests.utils import testutils


class TestServiceBusFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'servicebus_functions'

    @testutils.retryable_test(3, 5)
    def test_servicebus_basic(self):
        data = str(round(time.time()))
        r = self.webhost.request('POST', 'put_message',
                                 data=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # wait for trigger to process the queue item
            time.sleep(1)

            try:
                r = self.webhost.request('GET', 'get_servicebus_triggered')
                self.assertEqual(r.status_code, 200)
                msg = r.json()
                self.assertEqual(msg['body'], data)
                for attr in {'message_id', 'body', 'content_type', 'delivery_count',
                             'expiration_time', 'label', 'partition_key', 'reply_to',
                             'reply_to_session_id', 'scheduled_enqueue_time',
                             'session_id', 'time_to_live', 'to', 'user_properties',
                             'application_properties', 'correlation_id',
                             'dead_letter_error_description', 'dead_letter_reason',
                             'dead_letter_source', 'enqueued_sequence_number',
                             'enqueued_time_utc', 'expires_at_utc', 'locked_until',
                             'lock_token', 'sequence_number', 'state', 'subject',
                             'transaction_partition_key'}:
                    self.assertIn(attr, msg)
            except (AssertionError, json.JSONDecodeError):
                if try_no == max_retries - 1:
                    raise
            else:
                break


class TestServiceBusFunctionsStein(TestServiceBusFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'servicebus_functions' / \
            'servicebus_functions_stein'


class TestServiceBusFunctionsSteinGeneric(TestServiceBusFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'servicebus_functions' / \
            'servicebus_functions_stein' / 'generic'


@unittest.skipIf(sys.version_info.minor >= 14, "Skip to figure out uamqp.")
class TestServiceBusSDKFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'servicebus_functions' / \
            'servicebus_functions_sdk'

    @testutils.retryable_test(3, 5)
    def test_servicebus_basic_sdk(self):
        data = str(round(time.time()))
        r = self.webhost.request('POST', 'put_message_sdk',
                                 data=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # wait for trigger to process the queue item
            time.sleep(1)

            try:
                r = self.webhost.request('GET', 'get_servicebus_triggered_sdk')
                self.assertEqual(r.status_code, 200)
                msg = r.json()
                for attr in {'message', 'body', 'enqueued_time_utc', 'lock_token',
                             'message_id', 'sequence_number'}:
                    self.assertIn(attr, msg)
            except (AssertionError, json.JSONDecodeError):
                if try_no == max_retries - 1:
                    raise
            else:
                break

    @testutils.retryable_test(3, 5)
    def test_servicebus_deadletter_sdk(self):
        # The emulator does not support deadletter queues, so this test
        # just verifies that the function can be triggered and indexing succeeds
        data = str(round(time.time()))
        r = self.webhost.request('POST', 'put_message_sdk_deadletter',
                                 data=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # wait for trigger to process the queue item
            time.sleep(1)

            try:
                r = self.webhost.request('GET',
                                         'get_servicebus_triggered_sdk_deadletter')
                self.assertEqual(r.status_code, 200)
                msg = r.json()
                for attr in {'message', 'body', 'enqueued_time_utc', 'lock_token',
                             'message_id', 'sequence_number'}:
                    self.assertIn(attr, msg)
            except (AssertionError, json.JSONDecodeError):
                if try_no == max_retries - 1:
                    raise
            else:
                break
