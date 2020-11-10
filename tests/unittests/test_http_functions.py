# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import hashlib
import pathlib
import filecmp
import typing
import os
import unittest

import pytest

from azure_functions_worker import testutils


class TestHttpFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'http_functions'

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

    @unittest.skip("Reverting the debug logs PR as host currently cannot handle"
                   "apps with lot of debug statements. Reverting PR: "
                   "azure-functions-python-worker/pull/745")
    def test_debug_logging(self):
        r = self.webhost.request('GET', 'debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    @unittest.skip("Reverting the debug logs PR as host currently cannot handle"
                   "apps with lot of debug statements. Reverting PR: "
                   "azure-functions-python-worker/pull/745")
    def check_log_debug_logging(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging debug', host_out)
        self.assertIn('logging error', host_out)

    @unittest.skip("Reverting the debug logs PR as host currently cannot handle"
                   "apps with lot of debug statements. Reverting PR: "
                   "azure-functions-python-worker/pull/745")
    def test_debug_with_user_logging(self):
        r = self.webhost.request('GET', 'debug_user_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-user-debug')

    @unittest.skip("Reverting the debug logs PR as host currently cannot handle"
                   "apps with lot of debug statements. Reverting PR: "
                   "azure-functions-python-worker/pull/745")
    def check_log_debug_with_user_logging(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging debug', host_out)
        self.assertIn('logging error', host_out)

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
        self.assertIn('return_context', data['ctx_func_dir'])
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

    def test_import_module_troubleshooting_url(self):
        r = self.webhost.request('GET', 'missing_module/')
        self.assertEqual(r.status_code, 500)

    def check_log_import_module_troubleshooting_url(self,
                                                    host_out: typing.List[str]):
        self.assertIn("Exception: ModuleNotFoundError: "
                      "No module named 'does_not_exist'. "
                      "Troubleshooting Guide: "
                      "https://aka.ms/functions-modulenotfound", host_out)

    @pytest.mark.flaky(reruns=3)
    def test_print_logging_no_flush(self):
        r = self.webhost.request('GET', 'print_logging?message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    def check_log_print_logging_no_flush(self, host_out: typing.List[str]):
        self.assertIn('Secret42', host_out)

    @pytest.mark.flaky(reruns=3)
    def test_print_logging_with_flush(self):
        r = self.webhost.request('GET',
                                 'print_logging?flush=true&message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    def check_log_print_logging_with_flush(self, host_out: typing.List[str]):
        self.assertIn('Secret42', host_out)

    @pytest.mark.flaky(reruns=3)
    def test_print_to_console_stdout(self):
        r = self.webhost.request('GET',
                                 'print_logging?console=true&message=Secret42')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    @pytest.mark.flaky(reruns=3)
    def check_log_print_to_console_stdout(self, host_out: typing.List[str]):
        # System logs stdout should not exist in host_out
        self.assertNotIn('Secret42', host_out)

    def test_print_to_console_stderr(self):
        r = self.webhost.request('GET', 'print_logging?console=true'
                                 '&message=Secret42&is_stderr=true')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-print-logging')

    def check_log_print_to_console_stderr(self, host_out: typing.List[str],):
        # System logs stderr should not exist in host_out
        self.assertNotIn('Secret42', host_out)

    @pytest.mark.flaky(reruns=3)
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
