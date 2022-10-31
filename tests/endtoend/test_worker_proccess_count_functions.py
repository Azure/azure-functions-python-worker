# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
from threading import Thread
from unittest.mock import patch
from datetime import datetime
from tests.utils import testutils
from unittest import skip


class TestWorkerProcessCount1(testutils.WebHostTestCase):
    """Test the Http Trigger with setting up the python worker process count
    to 2. This test class will spawn a webhost from your
    <project_root>/build/webhost folder and replace the built-in Python with
    azure_functions_worker from your code base. this file is more focused
    on testing the E2E flow scenario for FUNCTIONS_WORKER_PROCESS_COUNT feature.
    """

    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_environ.start()
        super().setUp()

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ['PYTHON_THREADPOOL_THREAD_COUNT'] = '1'
        os_environ['FUNCTIONS_WORKER_PROCESS_COUNT'] = '1'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    @testutils.retryable_test(3, 5)
    def test_http_func_with_worker_process_count_1(self):
        res = [None, None]

        def http_req(response_num):
            r = self.webhost.request('GET', 'http_func')
            self.assertTrue(r.ok)
            res[response_num] = datetime.strptime(
                r.content.decode("utf-8"), "%H:%M:%S")

        # creating 2 different threads to send HTTP request
        trd1 = Thread(target=http_req, args=(0,))
        trd2 = Thread(target=http_req, args=(1,))
        trd1.start()
        trd2.start()
        trd1.join()
        trd2.join()
        '''time returned from both of the HTTP request should be greater than
        of equal to 1 since both the request should not be processed at the
        same time because FUNCTIONS_WORKER_PROCESS_COUNT is 1'''
        time_diff_in_seconds = abs((res[0] - res[1]).total_seconds())
        self.assertTrue(time_diff_in_seconds >= 1)


class TestWorkerProcessCount1Stein(TestWorkerProcessCount1):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' /\
                                            'http_functions_stein'


class TestWorkerProcessCount2(testutils.WebHostTestCase):
    """Test the Http Trigger with setting up the python worker process count
    to 2. This test class will spawn a webhost from your
    <project_root>/build/webhost folder and replace the built-in Python with
    azure_functions_worker from your code base. this file is more focused
    on testing the E2E flow scenario for FUNCTIONS_WORKER_PROCESS_COUNT feature.
    """

    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_environ.start()
        super().setUp()

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ['PYTHON_THREADPOOL_THREAD_COUNT'] = '1'
        os_environ['FUNCTIONS_WORKER_PROCESS_COUNT'] = '2'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    @testutils.retryable_test(3, 5)
    def test_http_func_with_worker_process_count_2(self):
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
        '''time returned from both of the HTTP request should be less than
        1 since both the request should be processed at the
        same time because FUNCTIONS_WORKER_PROCESS_COUNT is 2'''
        time_diff_in_seconds = abs((response[0] - response[1]).total_seconds())
        self.assertTrue(time_diff_in_seconds < 2)


@skip("skipping test for pystein worker process count 2")
class TestWorkerProcessCount2Stein(TestWorkerProcessCount2):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' /\
                                            'http_functions_stein'
