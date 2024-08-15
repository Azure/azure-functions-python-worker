# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import typing

from tests.utils import testutils
from tests.utils.testutils import TESTS_ROOT, remove_path

from azure_functions_worker.constants import PYTHON_ENABLE_DEBUG_LOGGING

HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO = """\
{
    "version": "2.0",
    "logging": {
        "logLevel": {
           "default": "Information"
        }
    },
    "functionTimeout": "00:05:00"
}
"""


@testutils.retryable_test(4, 5)
class TestDebugLoggingEnabledFunctions(testutils.WebHostTestCase):
    """
    Tests for cx debug logging enabled case.
    """
    @classmethod
    def setUpClass(cls):
        os.environ["PYTHON_ENABLE_DEBUG_LOGGING"] = "1"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        os.environ.pop(PYTHON_ENABLE_DEBUG_LOGGING)
        super().tearDownClass()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    def test_debug_logging_enabled(self):
        """
        Verify when cx debug logging is enabled, cx function debug logs
        are recorded in host logs.
        """
        r = self.webhost.request('GET', 'debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    def check_log_debug_logging_enabled(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging debug', host_out)
        self.assertIn('logging error', host_out)


class TestDebugLoggingDisabledFunctions(testutils.WebHostTestCase):
    """
    Tests for cx debug logging disabled case.
    """
    @classmethod
    def setUpClass(cls):
        os.environ["PYTHON_ENABLE_DEBUG_LOGGING"] = "0"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        os.environ.pop(PYTHON_ENABLE_DEBUG_LOGGING)
        super().tearDownClass()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    def test_debug_logging_disabled(self):
        """
        Verify when cx debug logging is disabled, cx function debug logs
        are not written to host logs.
        """
        r = self.webhost.request('GET', 'debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    def check_log_debug_logging_disabled(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging error', host_out)
        self.assertNotIn('logging debug', host_out)


class TestDebugLogEnabledHostFilteringFunctions(testutils.WebHostTestCase):
    """
    Tests for enable debug logging flag enabled and host log level is
    Information case.
    """
    @classmethod
    def setUpClass(cls):
        host_json = TESTS_ROOT / cls.get_script_dir() / 'host.json'

        with open(host_json, 'w+') as f:
            f.write(HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO)

        os.environ["PYTHON_ENABLE_DEBUG_LOGGING"] = "1"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        host_json = TESTS_ROOT / cls.get_script_dir() / 'host.json'
        remove_path(host_json)

        os.environ.pop(PYTHON_ENABLE_DEBUG_LOGGING)
        super().tearDownClass()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    def test_debug_logging_filtered(self):
        """
        Verify when cx debug logging is enabled and host logging level
        is Information, cx function debug logs are not written to host logs.
        """
        r = self.webhost.request('GET', 'debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    def check_log_debug_logging_filtered(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertNotIn('logging debug', host_out)
        self.assertIn('logging error', host_out)
