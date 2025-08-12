# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

from azure_functions_runtime_v1.utils.app_setting_manager import (
    get_python_appsetting_state)
from azure_functions_runtime_v1.utils.constants import (
    PYTHON_ENABLE_DEBUG_LOGGING,
    PYTHON_THREADPOOL_THREAD_COUNT,
)
from tests.utils import testutils
from unittest.mock import patch


class TestDefaultAppSettingsLogs(testutils.AsyncTestCase):
    """Tests for default app settings logs."""

    def test_get_python_appsetting_state(self):
        app_setting_state = get_python_appsetting_state()
        expected_string = ""
        self.assertEqual(expected_string, app_setting_state)


class TestNonDefaultAppSettingsLogs(testutils.AsyncTestCase):
    """Tests for non-default app settings logs."""

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ[PYTHON_THREADPOOL_THREAD_COUNT] = '20'
        os_environ[PYTHON_ENABLE_DEBUG_LOGGING] = '1'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    def test_get_python_appsetting_state(self):
        app_setting_state = get_python_appsetting_state()
        self.assertIn("PYTHON_THREADPOOL_THREAD_COUNT: 20 | ",
                      app_setting_state)
        self.assertIn("PYTHON_ENABLE_DEBUG_LOGGING: 1 | ", app_setting_state)
