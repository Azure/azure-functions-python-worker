# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import concurrent
import filecmp
import hashlib
import os
import pathlib
import requests
import sys
import typing
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import skipIf
from unittest.mock import patch

from tests.utils import testutils

from azure_functions_worker.constants import PYTHON_ENABLE_INIT_INDEXING

REQUEST_TIMEOUT_SEC = 5


@unittest.skipIf(sys.version_info.minor < 8, "HTTPv2"
                                             "is only supported for 3.8+.")
class TestHttpFunctionsWithInitIndexing(testutils.WebHostTestCase):
    @classmethod
    def setUpClass(cls):
        cls.env_variables[PYTHON_ENABLE_INIT_INDEXING] = '1'
        os.environ[PYTHON_ENABLE_INIT_INDEXING] = "1"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        os.environ.pop(PYTHON_ENABLE_INIT_INDEXING)
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


@unittest.skipIf(sys.version_info.minor <= 7, "Skipping tests <= Python 3.7")
class TestHttpFunctionsV2FastApi(testutils.WebHostTestCase):
    @classmethod
    def setUpClass(cls):
        cls._pre_env = dict(os.environ)
        os_environ = os.environ.copy()
        # Turn on feature flag
        os_environ[PYTHON_ENABLE_INIT_INDEXING] = '1'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        os.environ.clear()
        os.environ.update(cls._pre_env)
        cls._patch_environ.stop()
        super().tearDownClass()

    @classmethod
    def get_script_dir(cls):
        return testutils.EXTENSION_TESTS_FOLDER / 'http_v2_tests' / \
            'http_functions_v2' / \
            'fastapi'

    def test_return_bytes(self):
        r = self.webhost.request('GET', 'return_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'"Hello World"')
        self.assertEqual(r.headers['content-type'], 'application/json')

    def test_return_http_200(self):
        r = self.webhost.request('GET', 'return_http')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.headers['content-type'], 'text/html; charset=utf-8')

    def test_return_http_no_body(self):
        r = self.webhost.request('GET', 'return_http_no_body')
        self.assertEqual(r.text, '')
        self.assertEqual(r.status_code, 200)

    def test_return_http_auth_level_admin(self):
        r = self.webhost.request('GET', 'return_http_auth_admin',
                                 params={'code': 'testMasterKey'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.headers['content-type'], 'text/html; charset=utf-8')

    def test_return_http_404(self):
        r = self.webhost.request('GET', 'return_http_404')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.text, 'bye')

    def test_return_http_redirect(self):
        r = self.webhost.request('GET', 'return_http_redirect')
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.status_code, 200)

        r = self.webhost.request('GET', 'return_http_redirect',
                                 allow_redirects=False)
        self.assertEqual(r.status_code, 302)

    def test_async_return_str(self):
        r = self.webhost.request('GET', 'async_return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"Hello Async World!"')

    def test_async_logging(self):
        # Test that logging doesn't *break* things.
        r = self.webhost.request('GET', 'async_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-async"')

    def check_log_async_logging(self, host_out: typing.List[str]):
        # Host out only contains user logs
        self.assertIn('hello info', host_out)
        self.assertIn('and another error', host_out)

    @unittest.skipIf(sys.version_info.minor >= 7, "Skipping for ADO")
    def test_debug_logging(self):
        r = self.webhost.request('GET', 'debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-debug"')

    def check_log_debug_logging(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging error', host_out)
        self.assertNotIn('logging debug', host_out)

    @unittest.skipIf(sys.version_info.minor >= 7, "Skipping for ADO")
    def test_debug_with_user_logging(self):
        r = self.webhost.request('GET', 'debug_user_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-user-debug"')

    def check_log_debug_with_user_logging(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging debug', host_out)
        self.assertIn('logging error', host_out)

    def test_sync_logging(self):
        # Test that logging doesn't *break* things.
        r = self.webhost.request('GET', 'sync_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-sync"')

    def check_log_sync_logging(self, host_out: typing.List[str]):
        # Host out only contains user logs
        self.assertIn('a gracefully handled error', host_out)

    def test_return_context(self):
        r = self.webhost.request('GET', 'return_context')
        self.assertEqual(r.status_code, 200)

        data = r.json()

        self.assertEqual(data['method'], 'GET')
        self.assertEqual(data['ctx_func_name'], 'return_context')
        self.assertIn('ctx_invocation_id', data)
        self.assertIn('ctx_trace_context_Tracestate', data)
        self.assertIn('ctx_trace_context_Traceparent', data)

    def test_remapped_context(self):
        r = self.webhost.request('GET', 'remapped_context')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"GET"')

    def test_return_request(self):
        r = self.webhost.request(
            'GET', 'return_request',
            params={'a': 1, 'b': ':%)'},
            headers={'xxx': 'zzz', 'Max-Forwards': '10'})

        self.assertEqual(r.status_code, 200)

        req = r.json()

        self.assertEqual(req['method'], 'GET')
        self.assertEqual(req['params'], {'a': '1', 'b': ':%)'})
        self.assertEqual(req['headers']['xxx'], 'zzz')
        self.assertEqual(req['headers']['max-forwards'], '10')

        self.assertIn('return_request', req['url'])

    def test_post_return_request(self):
        r = self.webhost.request(
            'POST', 'return_request',
            params={'a': 1, 'b': ':%)'},
            headers={'xxx': 'zzz'},
            data={'key': 'value'})

        self.assertEqual(r.status_code, 200)

        req = r.json()

        self.assertEqual(req['method'], 'POST')
        self.assertEqual(req['params'], {'a': '1', 'b': ':%)'})
        self.assertEqual(req['headers']['xxx'], 'zzz')

        self.assertIn('return_request', req['url'])

        self.assertEqual(req['body'], 'key=value')

    def test_post_json_request_is_untouched(self):
        body = b'{"foo":  "bar", "two":  4}'
        body_hash = hashlib.sha256(body).hexdigest()
        r = self.webhost.request(
            'POST', 'return_request',
            headers={'Content-Type': 'application/json'},
            data=body)

        self.assertEqual(r.status_code, 200)
        req = r.json()
        self.assertEqual(req['body_hash'], body_hash)

    def test_accept_json(self):
        r = self.webhost.request(
            'GET', 'accept_json',
            json={'a': 'abc', 'd': 42})

        self.assertEqual(r.status_code, 200)
        r_json = r.json()
        self.assertEqual(r_json, {'a': 'abc', 'd': 42})
        self.assertEqual(r.headers['content-type'], 'application/json')

    def test_unhandled_error(self):
        r = self.webhost.request('GET', 'unhandled_error')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertIn('Exception: ZeroDivisionError', r.text)

    def check_log_unhandled_error(self,
                                  host_out: typing.List[str]):
        error_substring = 'ZeroDivisionError: division by zero'
        for item in host_out:
            if error_substring in item:
                break
        else:
            self.fail(
                f"{error_substring}' not found in host log.")

    def test_unhandled_urllib_error(self):
        r = self.webhost.request(
            'GET', 'unhandled_urllib_error',
            params={'img': 'http://example.com/nonexistent.jpg'})
        self.assertEqual(r.status_code, 500)

    def test_unhandled_unserializable_error(self):
        r = self.webhost.request(
            'GET', 'unhandled_unserializable_error')
        self.assertEqual(r.status_code, 500)

    def test_return_route_params(self):
        r = self.webhost.request('GET', 'return_route_params/foo/bar')
        self.assertEqual(r.status_code, 200)
        resp = r.json()
        self.assertEqual(resp, {'param1': 'foo', 'param2': 'bar'})

    def test_raw_body_bytes(self):
        parent_dir = pathlib.Path(__file__).parent
        image_file = parent_dir / 'resources/functions.png'
        with open(image_file, 'rb') as image:
            img = image.read()
            img_len = len(img)
            r = self.webhost.request('POST', 'raw_body_bytes', data=img)

        received_body_len = int(r.headers['body-len'])
        self.assertEqual(received_body_len, img_len)

        body = r.content
        try:
            received_img_file = parent_dir / 'received_img.png'
            with open(received_img_file, 'wb') as received_img:
                received_img.write(body)
            self.assertTrue(filecmp.cmp(received_img_file, image_file))
        finally:
            if (os.path.exists(received_img_file)):
                os.remove(received_img_file)

    def test_image_png_content_type(self):
        parent_dir = pathlib.Path(__file__).parent
        image_file = parent_dir / 'resources/functions.png'
        with open(image_file, 'rb') as image:
            img = image.read()
            img_len = len(img)
            r = self.webhost.request(
                'POST', 'raw_body_bytes',
                headers={'Content-Type': 'image/png'},
                data=img)

        received_body_len = int(r.headers['body-len'])
        self.assertEqual(received_body_len, img_len)

        body = r.content
        try:
            received_img_file = parent_dir / 'received_img.png'
            with open(received_img_file, 'wb') as received_img:
                received_img.write(body)
            self.assertTrue(filecmp.cmp(received_img_file, image_file))
        finally:
            if (os.path.exists(received_img_file)):
                os.remove(received_img_file)

    def test_application_octet_stream_content_type(self):
        parent_dir = pathlib.Path(__file__).parent
        image_file = parent_dir / 'resources/functions.png'
        with open(image_file, 'rb') as image:
            img = image.read()
            img_len = len(img)
            r = self.webhost.request(
                'POST', 'raw_body_bytes',
                headers={'Content-Type': 'application/octet-stream'},
                data=img)

        received_body_len = int(r.headers['body-len'])
        self.assertEqual(received_body_len, img_len)

        body = r.content
        try:
            received_img_file = parent_dir / 'received_img.png'
            with open(received_img_file, 'wb') as received_img:
                received_img.write(body)
            self.assertTrue(filecmp.cmp(received_img_file, image_file))
        finally:
            if (os.path.exists(received_img_file)):
                os.remove(received_img_file)

    def test_user_event_loop_error(self):
        # User event loop is not supported in HTTP trigger
        r = self.webhost.request('GET', 'user_event_loop/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-user-event-loop"')

    def check_log_user_event_loop_error(self, host_out: typing.List[str]):
        self.assertIn('try_log', host_out)

    def check_log_import_module_troubleshooting_url(self,
                                                    host_out: typing.List[str]):
        passed = False
        exception_message = "Exception: ModuleNotFoundError: "\
                            "No module named 'does_not_exist'. "\
                            "Cannot find module. "\
                            "Please check the requirements.txt file for the "\
                            "missing module. For more info, please refer the "\
                            "troubleshooting guide: "\
                            "https://aka.ms/functions-modulenotfound. "\
                            "Current sys.path: "
        for log in host_out:
            if exception_message in log:
                passed = True
        self.assertTrue(passed)

    def test_print_logging_no_flush(self):
        r = self.webhost.request('GET', 'print_logging?message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-print-logging"')

    def check_log_print_logging_no_flush(self, host_out: typing.List[str]):
        self.assertIn('Secret42', host_out)

    def test_print_logging_with_flush(self):
        r = self.webhost.request('GET',
                                 'print_logging?flush=true&message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-print-logging"')

    def check_log_print_logging_with_flush(self, host_out: typing.List[str]):
        self.assertIn('Secret42', host_out)

    def test_print_to_console_stdout(self):
        r = self.webhost.request('GET',
                                 'print_logging?console=true&message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-print-logging"')

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_multiple_cookie_header_in_response(self):
        r = self.webhost.request('GET', 'multiple_set_cookie_resp_headers')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get(
            'Set-Cookie'),
            "foo3=42; Domain=example.com; expires=Thu, 12 Jan 2017 13:55:08"
            " GMT; HttpOnly; Max-Age=10000000; Path=/; SameSite=Lax; Secure,"
            " foo3=43; Domain=example.com; expires=Fri, 12 Jan 2018 13:55:08"
            " GMT; HttpOnly; Max-Age=10000000; Path=/; SameSite=Lax; Secure")

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_set_cookie_header_in_response_default_value(self):
        r = self.webhost.request('GET',
                                 'set_cookie_resp_header_default_values')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Set-Cookie'),
                         'foo3=42; Path=/; SameSite=lax')

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_response_cookie_header_nullable_timestamp_err(self):
        r = self.webhost.request(
            'GET',
            'response_cookie_header_nullable_timestamp_err')
        self.assertEqual(r.status_code, 200)

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_response_cookie_header_nullable_bool_err(self):
        r = self.webhost.request(
            'GET',
            'response_cookie_header_nullable_bool_err')
        self.assertEqual(r.status_code, 200)
        self.assertTrue("Set-Cookie" in r.headers)

    def test_print_to_console_stderr(self):
        r = self.webhost.request('GET', 'print_logging?console=true'
                                        '&message=Secret42&is_stderr=true')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-print-logging"')

    def check_log_print_to_console_stderr(self, host_out: typing.List[str], ):
        # System logs stderr should not exist in host_out
        self.assertNotIn('Secret42', host_out)

    def test_hijack_current_event_loop(self):
        r = self.webhost.request('GET', 'hijack_current_event_loop/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"OK-hijack-current-event-loop"')

    def check_log_hijack_current_event_loop(self, host_out: typing.List[str]):
        # User logs should exist in host_out
        self.assertIn('parallelly_print', host_out)
        self.assertIn('parallelly_log_info at root logger', host_out)
        self.assertIn('parallelly_log_warning at root logger', host_out)
        self.assertIn('parallelly_log_error at root logger', host_out)
        self.assertIn('parallelly_log_exception at root logger', host_out)
        self.assertIn('parallelly_log_custom at custom_logger', host_out)
        self.assertIn('callsoon_log', host_out)

        # System logs should not exist in host_out
        self.assertNotIn('parallelly_log_system at disguised_logger', host_out)

    def test_no_type_hint(self):
        r = self.webhost.request('GET', 'no_type_hint')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '"no_type_hint"')

    def test_return_int(self):
        r = self.webhost.request('GET', 'return_int')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '1000')

    def test_return_float(self):
        r = self.webhost.request('GET', 'return_float')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '1000.0')

    def test_return_bool(self):
        r = self.webhost.request('GET', 'return_bool')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'true')

    def test_return_dict(self):
        r = self.webhost.request('GET', 'return_dict')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'key': 'value'})

    def test_return_list(self):
        r = self.webhost.request('GET', 'return_list')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), ["value1", "value2"])

    def test_return_pydantic_model(self):
        r = self.webhost.request('GET', 'return_pydantic_model')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'description': 'description1',
                                    'name': 'item1'})

    def test_return_pydantic_model_with_missing_fields(self):
        r = self.webhost.request('GET',
                                 'return_pydantic_model_with_missing_fields')
        self.assertEqual(r.status_code, 500)

    def check_return_pydantic_model_with_missing_fields(self,
                                                        host_out:
                                                        typing.List[str]):
        self.assertIn("Field required [type=missing, input_value={'name': "
                      "'item1'}, input_type=dict]", host_out)
