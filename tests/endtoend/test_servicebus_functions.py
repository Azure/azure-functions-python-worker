# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import os
import time
from unittest.mock import patch

from tests.utils import testutils


class TestServiceBusFunctions(testutils.WebHostTestCase):

    @classmethod
    def setUpClass(cls):
        cls.env_variables['PYTHON_SCRIPT_FILE_NAME'] = 'function_app.py'

        os_environ = os.environ.copy()
        os_environ.update(cls.env_variables)

        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

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


class TestServiceBusFunctionsSteinGeneric(TestServiceBusFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'servicebus_functions' / \
                                            'servicebus_functions_stein' / \
                                            'generic'
