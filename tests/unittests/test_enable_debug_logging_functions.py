# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing
import os
from unittest.mock import patch

from tests.utils import testutils
from tests.utils.testutils import TESTS_ROOT, remove_path

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
        cls.env_patcher = patch.dict(os.environ,
                                     {'PYTHON_ENABLE_DEBUG_LOGGING': '1'},
                                     clear=True)
        cls.env_patcher.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.env_patcher.stop()

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
        cls.env_patcher = patch.dict(os.environ,
                                     {'PYTHON_ENABLE_DEBUG_LOGGING': '0'},
                                     clear=True)
        cls.env_patcher.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.env_patcher.stop()

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
        cls.env_patcher = patch.dict(os.environ,
                                     {'PYTHON_ENABLE_DEBUG_LOGGING': '1'},
                                     clear=True)
        cls.env_patcher.start()
        host_json = TESTS_ROOT / cls.get_script_dir() / 'host.json'

        with open(host_json, 'w+') as f:
            f.write(HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO)

        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        host_json = TESTS_ROOT / cls.get_script_dir() / 'host.json'
        remove_path(host_json)

        super().tearDownClass()
        cls.env_patcher.stop()

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
