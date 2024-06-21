# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import concurrent
import os
from concurrent.futures import ThreadPoolExecutor

import requests

from azure_functions_worker.constants import (
    PYTHON_ENABLE_INIT_INDEXING, PYTHON_ISOLATE_WORKER_DEPENDENCIES)
from tests.utils import testutils

REQUEST_TIMEOUT_SEC = 5


class TestHttpV2FunctionsWithInitIndexing(testutils.WebHostTestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_variables[PYTHON_ENABLE_INIT_INDEXING] = '1'
        cls.env_variables[PYTHON_ISOLATE_WORKER_DEPENDENCIES] = '1'
        os.environ[PYTHON_ENABLE_INIT_INDEXING] = "1"
        os.environ[PYTHON_ISOLATE_WORKER_DEPENDENCIES] = "1"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        os.environ.pop(PYTHON_ENABLE_INIT_INDEXING)
        os.environ.pop(PYTHON_ISOLATE_WORKER_DEPENDENCIES)
        super().tearDownClass()

    @classmethod
    def get_environment_variables(cls):
        return cls.env_variables

    @classmethod
    def get_script_dir(cls):
        return testutils.EXTENSION_TESTS_FOLDER / 'http_v2_tests' / \
            'http_functions_v2' / \
            'fastapi'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azurefunctions-extensions-http-fastapi', 'orjson', 'ujson']

    @testutils.retryable_test(3, 5)
    def test_return_streaming(self):
        """Test if the return_streaming function returns a streaming
        response"""
        root_url = self.webhost._addr
        streaming_url = f'{root_url}/api/return_streaming'
        r = requests.get(
            streaming_url, timeout=REQUEST_TIMEOUT_SEC, stream=True)
        self.assertTrue(r.ok)
        # Validate streaming content
        expected_content = [b'First', b' chun', b'k\nSec', b'ond c', b'hunk\n']
        received_content = []
        for chunk in r.iter_content(chunk_size=5):
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
        self.assertEqual(r.headers['content-type'], 'application/json')
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
