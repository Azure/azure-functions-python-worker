# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing
import os
from unittest.mock import patch

from azure_functions_worker import testutils
from azure_functions_worker.constants import PYTHON_ENABLE_DEBUG_LOGGING
from azure_functions_worker.testutils import TESTS_ROOT, remove_path

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


class TestDebugLoggingEnabledFunctions(testutils.WebHostTestCase):
    """
    Tests for cx debug logging enabled case.
    """
    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ[PYTHON_ENABLE_DEBUG_LOGGING] = '1'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions'

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
        os_environ = os.environ.copy()
        os_environ[PYTHON_ENABLE_DEBUG_LOGGING] = '0'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions'

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

        os_environ = os.environ.copy()
        os_environ[PYTHON_ENABLE_DEBUG_LOGGING] = '1'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
        host_json = TESTS_ROOT / self.get_script_dir() / 'host.json'
        remove_path(host_json)

        super().tearDownClass()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions'

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
