# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import filecmp
import hashlib
import os
import pathlib
import requests
import sys
import typing
from unittest import skipIf
from unittest.mock import patch

from tests.utils import testutils

from azure_functions_worker.constants import PYTHON_ENABLE_INIT_INDEXING

REQUEST_TIMEOUT_SEC = 5


class TestHttpFunctions(testutils.WebHostTestCase):
    """Test the native Http Trigger in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. Since the Http Trigger is a native suport from host, we
    don't need to setup any external resources.
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

    def test_return_str(self):
        r = self.webhost.request('GET', 'return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello World!')
        self.assertTrue(r.headers['content-type'].startswith('text/plain'))

    def test_return_out(self):
        r = self.webhost.request('GET', 'return_out')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.text, 'hello')
        self.assertTrue(r.headers['content-type'].startswith('text/plain'))

    def test_return_bytes(self):
        r = self.webhost.request('GET', 'return_bytes')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertRegex(
        #    r.text, r'.*unsupported type .*http.* for Python type .*bytes.*')

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
        self.assertEqual(r.headers['content-type'],
                         'text/plain; charset=utf-8')

    def test_return_http_redirect(self):
        r = self.webhost.request('GET', 'return_http_redirect')
        self.assertEqual(r.text, '<h1>Hello World™</h1>')
        self.assertEqual(r.status_code, 200)

        r = self.webhost.request('GET', 'return_http_redirect',
                                 allow_redirects=False)
        self.assertEqual(r.status_code, 302)

    def test_no_return(self):
        r = self.webhost.request('GET', 'no_return')
        self.assertEqual(r.status_code, 204)

    def test_no_return_returns(self):
        r = self.webhost.request('GET', 'no_return_returns')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertRegex(r.text,
        #                  r'.*function .+no_return_returns.+ without a '
        #                  r'\$return binding returned a non-None value.*')

    def test_async_return_str(self):
        r = self.webhost.request('GET', 'async_return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello Async World!')

    def test_async_logging(self):
        # Test that logging doesn't *break* things.
        r = self.webhost.request('GET', 'async_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-async')

    def check_log_async_logging(self, host_out: typing.List[str]):
        # Host out only contains user logs
        self.assertIn('hello info', host_out)
        self.assertIn('and another error', host_out)

    def test_sync_logging(self):
        # Test that logging doesn't *break* things.
        r = self.webhost.request('GET', 'sync_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-sync')

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
        self.assertEqual(r.text, 'GET')

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

        self.assertEqual(req['get_body'], 'key=value')

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
            'POST', 'accept_json',
            json={'a': 'abc', 'd': 42})

        req = r.json()

        self.assertEqual(req['method'], 'POST')
        self.assertEqual(req['get_json'], {'a': 'abc', 'd': 42})

        self.assertIn('accept_json', req['url'])

    def test_unhandled_error(self):
        r = self.webhost.request('GET', 'unhandled_error')
        self.assertEqual(r.status_code, 500)
        # https://github.com/Azure/azure-functions-host/issues/2706
        # self.assertIn('Exception: ZeroDivisionError', r.text)

    def check_log_unhandled_error(self,
                                  host_out: typing.List[str]):
        self.assertIn('Exception: ZeroDivisionError: division by zero',
                      host_out)

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
        self.assertEqual(r.text, 'OK-user-event-loop')

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

    @testutils.retryable_test(3, 5)
    def test_print_logging_no_flush(self):
        r = self.webhost.request('GET', 'print_logging?message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    @testutils.retryable_test(3, 5)
    def check_log_print_logging_no_flush(self, host_out: typing.List[str]):
        self.assertIn('Secret42', host_out)

    @testutils.retryable_test(3, 5)
    def test_print_logging_with_flush(self):
        r = self.webhost.request('GET',
                                 'print_logging?flush=true&message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    @testutils.retryable_test(3, 5)
    def check_log_print_logging_with_flush(self, host_out: typing.List[str]):
        self.assertIn('Secret42', host_out)

    def test_print_to_console_stdout(self):
        r = self.webhost.request('GET',
                                 'print_logging?console=true&message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_multiple_cookie_header_in_response(self):
        r = self.webhost.request('GET', 'multiple_set_cookie_resp_headers')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get(
            'Set-Cookie'),
            "foo3=42; expires=Thu, 12 Jan 2017 13:55:08 GMT; "
            "max-age=10000000; domain=example.com; path=/; secure; httponly, "
            "foo3=43; expires=Fri, 12 Jan 2018 13:55:08 GMT; "
            "max-age=10000000; domain=example.com; path=/; secure; httponly")

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_set_cookie_header_in_response_empty_value(self):
        r = self.webhost.request('GET', 'set_cookie_resp_header_empty')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Set-Cookie'), None)

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_set_cookie_header_in_response_default_value(self):
        r = self.webhost.request('GET',
                                 'set_cookie_resp_header_default_values')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get('Set-Cookie'),
                         'foo=bar; domain=; path=')

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_response_cookie_header_nullable_timestamp_err(self):
        r = self.webhost.request(
            'GET',
            'response_cookie_header_nullable_timestamp_err')
        self.assertEqual(r.status_code, 500)

    def check_log_response_cookie_header_nullable_timestamp_err(self,
                                                                host_out:
                                                                typing.List[
                                                                    str]):
        self.assertIn(
            "Can not parse value Dummy of expires in the cookie due to "
            "invalid format.",
            host_out)

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_response_cookie_header_nullable_bool_err(self):
        r = self.webhost.request(
            'GET',
            'response_cookie_header_nullable_bool_err')
        self.assertEqual(r.status_code, 200)
        self.assertFalse("Set-Cookie" in r.headers)

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_response_cookie_header_nullable_double_err(self):
        r = self.webhost.request(
            'GET',
            'response_cookie_header_nullable_double_err')
        self.assertEqual(r.status_code, 200)
        self.assertFalse("Set-Cookie" in r.headers)

    def check_log_print_to_console_stdout(self, host_out: typing.List[str]):
        # System logs stdout should not exist in host_out
        self.assertNotIn('Secret42', host_out)

    def test_print_to_console_stderr(self):
        r = self.webhost.request('GET', 'print_logging?console=true'
                                        '&message=Secret42&is_stderr=true')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    def check_log_print_to_console_stderr(self, host_out: typing.List[str], ):
        # System logs stderr should not exist in host_out
        self.assertNotIn('Secret42', host_out)

    def test_hijack_current_event_loop(self):
        r = self.webhost.request('GET', 'hijack_current_event_loop/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-hijack-current-event-loop')

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

    @skipIf(sys.version_info.minor < 11,
            "The context param is only available for 3.11+")
    def test_create_task_with_context(self):
        r = self.webhost.request('GET', 'create_task_with_context')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Finished Hello World in 5'
                                 ' | Finished Hello World in 10')

    def test_create_task_without_context(self):
        r = self.webhost.request('GET', 'create_task_without_context')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Finished Hello World in 5')


class TestHttpFunctionsStein(TestHttpFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein'

    def test_no_return(self):
        r = self.webhost.request('GET', 'no_return')
        self.assertEqual(r.status_code, 500)

    def test_no_return_returns(self):
        r = self.webhost.request('GET', 'no_return_returns')
        self.assertEqual(r.status_code, 200)


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

        self.assertIn("numpy version", r.content.decode("UTF-8"))

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
