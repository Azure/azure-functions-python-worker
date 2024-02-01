# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time

from tests.utils import testutils


class TestServiceBusFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'servicebus_functions'

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
            except (AssertionError, json.JSONDecodeError):
                if try_no == max_retries - 1:
                    raise
            else:
                break


class TestServiceBusFunctionsStein(TestServiceBusFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'servicebus_functions' / \
                                            'servicebus_functions_stein'

    @testutils.retryable_test(3, 5)
    def test_servicebus_batch(self):
        data = '{"value": "2024-01-19T12:50:41.250941Z"}'
        r = self.webhost.request('POST', 'put_message_batch',
                                 data=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        time.sleep(2)

        r = self.webhost.request('GET', 'get_servicebus_triggered_batch')
        self.assertEqual(r.status_code, 200)
        msg = r.json()
        self.assertEqual(msg["body"], data)


class TestServiceBusFunctionsSteinGeneric(TestServiceBusFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'servicebus_functions' / \
                                            'servicebus_functions_stein' / \
                                            'generic'
