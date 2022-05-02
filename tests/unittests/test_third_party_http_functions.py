# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License
import filecmp
import os
import pathlib
import re
import typing
from unittest.mock import patch

from azure_functions_worker import testutils
from azure_functions_worker.testutils import UNIT_TESTS_ROOT

HOST_JSON_TEMPLATE = """\
{
    "version": "2.0",
    "logging": {
        "logLevel": {
           "default": "Trace"
        }
    },
    "extensions": {
        "http": {
          "routePrefix": ""
        }
    },
    "functionTimeout": "00:05:00"
}
"""


class ThirdPartyHttpFunctionsTestBase:
    class TestThirdPartyHttpFunctions(testutils.WebHostTestCase):

        @classmethod
        def setUpClass(cls):
            host_json = cls.get_script_dir() / 'host.json'
            with open(host_json, 'w+') as f:
                f.write(HOST_JSON_TEMPLATE)
            os_environ = os.environ.copy()
            # Turn on feature flag
            os_environ['AzureWebJobsFeatureFlags'] = 'EnableWorkerIndexing'
            cls._patch_environ = patch.dict('os.environ', os_environ)
            cls._patch_environ.start()
            super().setUpClass()

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            cls._patch_environ.stop()

        @classmethod
        def get_script_dir(cls):
            pass

        def test_debug_logging(self):
            r = self.webhost.request('GET', 'debug_logging', no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, 'OK-debug')

        def check_log_debug_logging(self, host_out: typing.List[str]):
            self.assertIn('logging info', host_out)
            self.assertIn('logging warning', host_out)
            self.assertIn('logging error', host_out)
            self.assertNotIn('logging debug', host_out)

        def test_debug_with_user_logging(self):
            r = self.webhost.request('GET', 'debug_user_logging',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, 'OK-user-debug')

        def check_log_debug_with_user_logging(self,
                                              host_out: typing.List[str]):
            self.assertIn('logging info', host_out)
            self.assertIn('logging warning', host_out)
            self.assertIn('logging debug', host_out)
            self.assertIn('logging error', host_out)

        def test_print_logging_no_flush(self):
            r = self.webhost.request('GET', 'print_logging?message=Secret42',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, 'OK-print-logging')

        def check_log_print_logging_no_flush(self, host_out: typing.List[str]):
            self.assertIn('Secret42', host_out)

        def test_print_logging_with_flush(self):
            r = self.webhost.request('GET',
                                     'print_logging?flush=true&message'
                                     '=Secret42',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, 'OK-print-logging')

        def check_log_print_logging_with_flush(self,
                                               host_out: typing.List[str]):
            self.assertIn('Secret42', host_out)

        def test_print_to_console_stdout(self):
            r = self.webhost.request('GET',
                                     'print_logging?console=true&message'
                                     '=Secret42',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, 'OK-print-logging')

        def check_log_print_to_console_stdout(self,
                                              host_out: typing.List[str]):
            # System logs stdout should not exist in host_out
            self.assertNotIn('Secret42', host_out)

        def test_print_to_console_stderr(self):
            r = self.webhost.request('GET', 'print_logging?console=true'
                                            '&message=Secret42&is_stderr=true',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, 'OK-print-logging')

        def check_log_print_to_console_stderr(self,
                                              host_out: typing.List[str], ):
            # System logs stderr should not exist in host_out
            self.assertNotIn('Secret42', host_out)

        def test_raw_body_bytes(self):
            parent_dir = pathlib.Path(__file__).parent.parent
            image_file = parent_dir / 'unittests/resources/functions.png'
            with open(image_file, 'rb') as image:
                img = image.read()
                img_len = len(img)
                r = self.webhost.request('POST', 'raw_body_bytes', data=img,
                                         no_prefix=True)

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

        def test_return_http_no_body(self):
            r = self.webhost.request('GET', 'return_http_no_body',
                                     no_prefix=True)
            self.assertEqual(r.text, '')
            self.assertEqual(r.status_code, 200)

        def test_return_http_redirect(self):
            r = self.webhost.request('GET', 'return_http_redirect',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.text, '<h1>Hello World™</h1>')

            r = self.webhost.request('GET', 'return_http_redirect',
                                     allow_redirects=False, no_prefix=True)
            self.assertEqual(r.status_code, 302)

        def test_unhandled_error(self):
            r = self.webhost.request('GET', 'unhandled_error', no_prefix=True)
            self.assertEqual(r.status_code, 500)
            # https://github.com/Azure/azure-functions-host/issues/2706
            # self.assertIn('ZeroDivisionError', r.text)

        def check_log_unhandled_error(self,
                                      host_out: typing.List[str]):
            r = re.compile(".*ZeroDivisionError: division by zero.*")
            error_log = list(filter(r.match, host_out))
            self.assertGreaterEqual(len(error_log), 1)

        def test_unhandled_unserializable_error(self):
            r = self.webhost.request(
                'GET', 'unhandled_unserializable_error', no_prefix=True)
            self.assertEqual(r.status_code, 500)

        def test_unhandled_urllib_error(self):
            r = self.webhost.request(
                'GET', 'unhandled_urllib_error',
                params={'img': 'http://example.com/nonexistent.jpg'},
                no_prefix=True)
            self.assertEqual(r.status_code, 500)


class TestAsgiHttpFunctions(
        ThirdPartyHttpFunctionsTestBase.TestThirdPartyHttpFunctions):
    @classmethod
    def get_script_dir(cls):
        return UNIT_TESTS_ROOT / 'third_party_http_functions' / 'stein' / \
            'asgi_function'

    def test_hijack_current_event_loop(self):
        r = self.webhost.request('GET', 'hijack_current_event_loop',
                                 no_prefix=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-hijack-current-event-loop')

    def check_log_hijack_current_event_loop(self,
                                            host_out: typing.List[str]):
        # User logs should exist in host_out
        self.assertIn('parallelly_print', host_out)
        self.assertIn('parallelly_log_info at root logger', host_out)
        self.assertIn('parallelly_log_warning at root logger', host_out)
        self.assertIn('parallelly_log_error at root logger', host_out)
        self.assertIn('parallelly_log_exception at root logger',
                      host_out)
        self.assertIn('parallelly_log_custom at custom_logger', host_out)
        self.assertIn('callsoon_log', host_out)

        # System logs should not exist in host_out
        self.assertNotIn('parallelly_log_system at disguised_logger',
                         host_out)


class TestWsgiHttpFunctions(
        ThirdPartyHttpFunctionsTestBase.TestThirdPartyHttpFunctions):
    @classmethod
    def get_script_dir(cls):
        return UNIT_TESTS_ROOT / 'third_party_http_functions' / 'stein' / \
            'wsgi_function'
