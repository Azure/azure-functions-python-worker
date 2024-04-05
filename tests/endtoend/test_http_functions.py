# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import concurrent
import os
import sys
import typing
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import requests

from azure_functions_worker.constants import PYTHON_ENABLE_INIT_INDEXING
from tests.utils import testutils

REQUEST_TIMEOUT_SEC = 5


class TestHttpFunctions(testutils.WebHostTestCase):
    """Test the native Http Trigger in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. Since the Http Trigger is a native suport from host, we
    don't need to setup any external resources.

    Compared to the unittests/test_http_functions.py, this file is more focus
    on testing the E2E flow scenarios.
    """

    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_environ.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    @testutils.retryable_test(3, 5)
    def test_function_index_page_should_return_ok(self):
        """The index page of Azure Functions should return OK in any
        circumstances
        """
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_default_http_template_should_return_ok(self):
        """Test if the default template of Http trigger in Python Function app
        will return OK
        """
        r = self.webhost.request('GET', 'default_template',
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_default_http_template_should_accept_query_param(self):
        """Test if the azure.functions SDK is able to deserialize query
        parameter from the default template
        """
        r = self.webhost.request('GET', 'default_template',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query. This HTTP triggered function executed successfully.'
        )

    @testutils.retryable_test(3, 5)
    def test_default_http_template_should_accept_body(self):
        """Test if the azure.functions SDK is able to deserialize http body
        and pass it to default template
        """
        r = self.webhost.request('POST', 'default_template',
                                 data='{ "name": "body" }'.encode('utf-8'),
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, body. This HTTP triggered function executed successfully.'
        )

    @testutils.retryable_test(3, 5)
    def test_worker_status_endpoint_should_return_ok(self):
        """Test if the worker status endpoint will trigger
        _handle__worker_status_request and sends a worker status response back
        to host
        """
        root_url = self.webhost._addr
        health_check_url = f'{root_url}/admin/host/ping'
        r = requests.post(health_check_url,
                          params={'checkHealth': '1'},
                          timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_worker_status_endpoint_should_return_ok_when_disabled(self):
        """Test if the worker status endpoint will trigger
        _handle__worker_status_request and sends a worker status response back
        to host
        """
        os.environ['WEBSITE_PING_METRICS_SCALE_ENABLED'] = '0'
        root_url = self.webhost._addr
        health_check_url = f'{root_url}/admin/host/ping'
        r = requests.post(health_check_url,
                          params={'checkHealth': '1'},
                          timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)


class TestHttpFunctionsStein(TestHttpFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein'


class TestHttpFunctionsSteinGeneric(TestHttpFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein' / \
                                            'generic'


class TestCommonLibsHttpFunctions(testutils.WebHostTestCase):
    """Test the common libs scenarios in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. this file is more focus on testing the E2E flow scenarios.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'common_libs_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['requests', 'python-dotenv', "plotly", "scikit-learn",
                "opencv-python", "pandas", "numpy"]

    @testutils.retryable_test(3, 5)
    def test_numpy(self):
        r = self.webhost.request('GET', 'numpy_func',
                                 timeout=REQUEST_TIMEOUT_SEC)

        res = "array: [1.+0.j 2.+0.j]"

        self.assertEqual(r.content.decode("UTF-8"), res)

    def test_requests(self):
        r = self.webhost.request('GET', 'requests_func',
                                 timeout=10)

        self.assertTrue(r.ok)
        self.assertEqual(r.content.decode("UTF-8"), 'req status code: 200')

    def test_pandas(self):
        r = self.webhost.request('GET', 'pandas_func',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertIn("two-dimensional",
                      r.content.decode("UTF-8"))

    def test_sklearn(self):
        r = self.webhost.request('GET', 'sklearn_func',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertIn("First 5 records of array:",
                      r.content.decode("UTF-8"))

    def test_opencv(self):
        r = self.webhost.request('GET', 'opencv_func',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertIn("opencv version:",
                      r.content.decode("UTF-8"))

    def test_dotenv(self):
        r = self.webhost.request('GET', 'dotenv_func',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertEqual(r.content.decode("UTF-8"), "found")

    def test_plotly(self):
        r = self.webhost.request('GET', 'plotly_func',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertIn("plotly version:",
                      r.content.decode("UTF-8"))


class TestCommonLibsHttpFunctionsStein(TestCommonLibsHttpFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'common_libs_functions' / \
                                            'common_libs_functions_stein'


class TestHttpFunctionsWithInitIndexing(TestHttpFunctions):

    @classmethod
    def setUpClass(cls):
        os.environ[PYTHON_ENABLE_INIT_INDEXING] = "1"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Remove the PYTHON_SCRIPT_FILE_NAME environment variable
        os.environ.pop(PYTHON_ENABLE_INIT_INDEXING)
        super().tearDownClass()


@unittest.skipIf(sys.version_info <= (3, 7), "Skipping tests if <= Python 3.7")
class TestHttpFunctionsV2FastApiWithInitIndexing(TestHttpFunctionsWithInitIndexing):
        @classmethod
        def get_script_dir(cls):
            return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                                'http_functions_v2' / \
                                                'fastapi'

        @testutils.retryable_test(3, 5)
        def test_return_streaming(self):
            """Test if the return_streaming function returns a streaming
            response"""
            root_url = self.webhost._addr
            streaming_url = f'{root_url}/api/return_streaming'
            r = requests.get(streaming_url, timeout=REQUEST_TIMEOUT_SEC, stream=True)
            self.assertTrue(r.ok)
            # Validate streaming content
            expected_content = [b"First chunk\n", b"Second chunk\n"]
            received_content = []
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    received_content.append(chunk)
            self.assertEqual(received_content, expected_content)

        @testutils.retryable_test(3, 5)
        def test_return_streaming_concurrently(self):
            """Test if the return_streaming function returns a streaming
            response concurrently"""
            root_url = self.webhost._addr
            streaming_url = f'{root_url}/return_streaming'

            # Function to make a streaming request and validate content
            def make_request():
                r = requests.get(streaming_url, timeout=REQUEST_TIMEOUT_SEC,
                                 stream=True)
                self.assertTrue(r.ok)
                expected_content = [b"First chunk\n", b"Second chunk\n"]
                received_content = []
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        received_content.append(chunk)
                self.assertEqual(received_content, expected_content)

            # Make concurrent requests
            with ThreadPoolExecutor(max_workers=2) as executor:
                executor.map(make_request, range(2))

        @testutils.retryable_test(3, 5)
        def test_return_html(self):
            """Test if the return_html function returns an HTML response"""
            root_url = self.webhost._addr
            html_url = f'{root_url}/api/return_html'
            r = requests.get(html_url, timeout=REQUEST_TIMEOUT_SEC)
            self.assertTrue(r.ok)
            self.assertEqual(r.headers['content-type'],
                             'text/html; charset=utf-8')
            # Validate HTML content
            expected_html = "<html><body><h1>Hello, World!</h1></body></html>"
            self.assertEqual(r.text, expected_html)

        @testutils.retryable_test(3, 5)
        def test_return_ujson(self):
            """Test if the return_ujson function returns a UJSON response"""
            root_url = self.webhost._addr
            ujson_url = f'{root_url}/api/return_ujson'
            r = requests.get(ujson_url, timeout=REQUEST_TIMEOUT_SEC)
            self.assertTrue(r.ok)
            self.assertEqual(r.headers['content-type'],'application/json')
            self.assertEqual(r.text, '{"message":"Hello, World!"}')

        @testutils.retryable_test(3, 5)
        def test_return_orjson(self):
            """Test if the return_orjson function returns an ORJSON response"""
            root_url = self.webhost._addr
            orjson_url = f'{root_url}/api/return_orjson'
            r = requests.get(orjson_url, timeout=REQUEST_TIMEOUT_SEC)
            self.assertTrue(r.ok)
            self.assertEqual(r.headers['content-type'], 'application/json')
            self.assertEqual(r.text, '{"message":"Hello, World!"}')

        @testutils.retryable_test(3, 5)
        def test_return_file(self):
            """Test if the return_file function returns a file response"""
            root_url = self.webhost._addr
            file_url = f'{root_url}/api/return_file'
            r = requests.get(file_url, timeout=REQUEST_TIMEOUT_SEC)
            self.assertTrue(r.ok)
            self.assertIn('@app.route(route="default_template")', r.text)

        @testutils.retryable_test(3, 5)
        def test_upload_data_stream(self):
            """Test if the upload_data_stream function receives streaming data
            and returns the complete data"""
            root_url = self.webhost._addr
            upload_url = f'{root_url}/api/upload_data_stream'

            # Define the streaming data
            data_chunks = [b"First chunk\n", b"Second chunk\n"]

            # Define a function to simulate streaming by reading from an
            # iterator
            def stream_data(data_chunks):
                for chunk in data_chunks:
                    yield chunk

            # Send a POST request with streaming data
            r = requests.post(upload_url, data=stream_data(data_chunks))

            # Assert that the request was successful
            self.assertTrue(r.ok)

            # Assert that the response content matches the concatenation of
            # all data chunks
            complete_data = b"".join(data_chunks)
            self.assertEqual(r.content, complete_data)

        @testutils.retryable_test(3, 5)
        def test_upload_data_stream_concurrently(self):
            """Test if the upload_data_stream function receives streaming data
            and returns the complete data"""
            root_url = self.webhost._addr
            upload_url = f'{root_url}/api/upload_data_stream'

            # Define the streaming data
            data_chunks = [b"First chunk\n", b"Second chunk\n"]

            # Define a function to simulate streaming by reading from an
            # iterator
            def stream_data(data_chunks):
                for chunk in data_chunks:
                    yield chunk

            # Define the number of concurrent requests
            num_requests = 5

            # Define a function to send a single request
            def send_request():
                r = requests.post(upload_url, data=stream_data(data_chunks))
                return r.ok, r.content

            # Send multiple requests concurrently
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [executor.submit(send_request) for _ in
                           range(num_requests)]

            # Assert that all requests were successful and the response
            # contents are correct
            for future in concurrent.futures.as_completed(futures):
                ok, content = future.result()
                self.assertTrue(ok)
                complete_data = b"".join(data_chunks)
                self.assertEqual(content, complete_data)

class TestUserThreadLoggingHttpFunctions(testutils.WebHostTestCase):
    """Test the Http trigger that contains logging with user threads.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. this file is more focus on testing the E2E flow scenarios.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'user_thread_logging'

    @testutils.retryable_test(3, 5)
    def test_http_thread(self):
        r = self.webhost.request('GET', 'thread',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertTrue(r.ok)

    def check_log_http_thread(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count('Before threads.'), 1)
        self.assertEqual(host_out.count('Thread1 used.'), 1)
        self.assertEqual(host_out.count('Thread2 used.'), 1)
        self.assertEqual(host_out.count('Thread3 used.'), 1)
        self.assertEqual(host_out.count('After threads.'), 1)

    @testutils.retryable_test(3, 5)
    def test_http_async_thread(self):
        r = self.webhost.request('GET', 'async_thread',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertTrue(r.ok)

    def check_log_http_async_thread(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count('Before threads.'), 1)
        self.assertEqual(host_out.count('Thread1 used.'), 1)
        self.assertEqual(host_out.count('Thread2 used.'), 1)
        self.assertEqual(host_out.count('Thread3 used.'), 1)
        self.assertEqual(host_out.count('After threads.'), 1)

    @testutils.retryable_test(3, 5)
    def test_http_thread_pool_executor(self):
        r = self.webhost.request('GET', 'thread_pool_executor',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertTrue(r.ok)

    def check_log_http_thread_pool_executor(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count('Before TPE.'), 1)
        self.assertEqual(host_out.count('Using TPE.'), 1)
        self.assertEqual(host_out.count('After TPE.'), 1)

    @testutils.retryable_test(3, 5)
    def test_http_async_thread_pool_executor(self):
        r = self.webhost.request('GET', 'async_thread_pool_executor',
                                 timeout=REQUEST_TIMEOUT_SEC)

        self.assertTrue(r.ok)

    def check_log_http_async_thread_pool_executor(self,
                                                  host_out: typing.List[str]):
        self.assertEqual(host_out.count('Before TPE.'), 1)
        self.assertEqual(host_out.count('Using TPE.'), 1)
        self.assertEqual(host_out.count('After TPE.'), 1)
