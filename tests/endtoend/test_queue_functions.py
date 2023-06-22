# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time

import pytest

from tests.utils import testutils

@pytest.mark.xdist_group(name="group2")
class TestQueueFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'queue_functions'

    def test_queue_basic(self):
        r = self.webhost.request('POST', 'put_queue',
                                 data='test-message')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # wait for queue_trigger to process the queue item
        time.sleep(1)

        r = self.webhost.request('GET', 'get_queue_blob')
        self.assertEqual(r.status_code, 200)
        msg_info = r.json()

        self.assertIn('queue', msg_info)
        msg = msg_info['queue']

        self.assertEqual(msg['body'], 'test-message')
        for attr in {'id', 'expiration_time', 'insertion_time',
                     'time_next_visible', 'pop_receipt', 'dequeue_count'}:
            self.assertIsNotNone(msg.get(attr))

    def test_queue_return(self):
        r = self.webhost.request('POST', 'put_queue_return',
                                 data='test-message-return')
        self.assertEqual(r.status_code, 200)

        # wait for queue_trigger to process the queue item
        time.sleep(1)

        r = self.webhost.request('GET', 'get_queue_blob_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-message-return')

    def test_queue_message_object_return(self):
        r = self.webhost.request('POST', 'put_queue_message_return',
                                 data='test-message-object-return')
        self.assertEqual(r.status_code, 200)

        # wait for queue_trigger to process the queue item
        time.sleep(1)

        r = self.webhost.request('GET', 'get_queue_blob_message_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-message-object-return')

    def test_queue_untyped_return(self):
        r = self.webhost.request('POST', 'put_queue_untyped_return',
                                 data='test-untyped-return')
        self.assertEqual(r.status_code, 200)

        # wait for queue_trigger to process the queue item
        time.sleep(1)

        r = self.webhost.request('GET', 'get_queue_untyped_blob_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-untyped-return')

    def test_queue_return_multiple(self):
        r = self.webhost.request('POST', 'put_queue_return_multiple',
                                 data='foo')
        self.assertTrue(200 <= r.status_code < 300,
                        f"Returned status code {r.status_code}, "
                        "not in the 200-300 range.")

        # wait for queue_trigger to process the queue item
        time.sleep(1)

    def test_queue_return_multiple_outparam(self):
        r = self.webhost.request('POST', 'put_queue_multiple_out',
                                 data='foo')
        self.assertTrue(200 <= r.status_code < 300,
                        f"Returned status code {r.status_code}, "
                        "not in the 200-300 range.")
        self.assertEqual(r.text, 'HTTP response: foo')


@pytest.mark.xdist_group(name="group2")
class TestQueueFunctionsStein(TestQueueFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'queue_functions' / \
                                            'queue_functions_stein'


@pytest.mark.xdist_group(name="group2")
class TestQueueFunctionsSteinGeneric(TestQueueFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'queue_functions' / \
            'queue_functions_stein' / 'generic'
