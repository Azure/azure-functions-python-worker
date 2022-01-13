# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing
import os
from unittest.mock import patch

from azure_functions_worker import testutils
from azure_functions_worker.constants import PYTHON_ENABLE_DEBUG_LOGGING


class TestDebugLoggingEnabledFunctions(testutils.WebHostTestCase):
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
        return testutils.UNIT_TESTS_FOLDER / 'enable_debug_logging_functions'

    def test_debug_logging_enabled(self):
        r = self.webhost.request('GET', 'enable_debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    def check_log_debug_logging_enabled(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging debug', host_out)
        self.assertIn('logging error', host_out)


class TestDebugLoggingDisabledFunctions(testutils.WebHostTestCase):
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
        return testutils.UNIT_TESTS_FOLDER / 'enable_debug_logging_functions'

    def test_debug_logging_disabled(self):
        r = self.webhost.request('GET', 'enable_debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    def check_log_debug_logging_disabled(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging error', host_out)
        self.assertNotIn('logging debug', host_out)
