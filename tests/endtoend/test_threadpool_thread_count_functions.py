# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import os
from threading import Thread
from unittest.mock import patch
from datetime import datetime

import pytest

from tests.utils import testutils
import time


class TestPythonThreadpoolThreadCount(testutils.WebHostTestCase):
    """ Test the Http Trigger with setting up the python threadpool thread
    count to 2. this test will check if both requests should be processed
    at the same time. this file is more focus on testing the E2E flow
    scenarios.
    """

    @classmethod
    def setUpClass(cls):
        cls.env_variables['PYTHON_THREADPOOL_THREAD_COUNT'] = '2'

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
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    @pytest.mark.order(4)
    def test_http_func_with_thread_count(self):
        max_retries = 5
        interval = 8
        retry_count = 0
        while retry_count < max_retries:
            response = [None, None]

            def http_req(res_num):
                r = self.webhost.request('GET', 'http_func')
                self.assertTrue(r.ok)
                response[res_num] = datetime.strptime(
                    r.content.decode("utf-8"), "%H:%M:%S")

            # creating 2 different threads to send HTTP request
            thread1 = Thread(target=http_req, args=(0,))
            thread2 = Thread(target=http_req, args=(1,))
            thread1.start()
            thread2.start()
            thread1.join()
            thread2.join()
            """function execution time difference between both HTTP request
            should be less than 1 since both the request should be processed at
            the same time because PYTHON_THREADPOOL_THREAD_COUNT is 2.
            """
            if response[0] and response[1]:
                time_diff_in_seconds = abs(
                    (response[0] - response[1]).total_seconds())
                self.assertTrue(time_diff_in_seconds < 1)
                break
            else:
                retry_count += 1
                time.sleep(interval)

        self.assertTrue(retry_count < max_retries)


class TestPythonThreadpoolThreadCountStein(TestPythonThreadpoolThreadCount):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein'
