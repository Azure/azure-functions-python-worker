# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import collections as col
import os
from unittest.mock import patch

from azure_functions_worker.constants import (
    PYTHON_ENABLE_DEBUG_LOGGING,
    PYTHON_THREADPOOL_THREAD_COUNT,
)
from azure_functions_worker.utils.app_setting_manager import get_python_appsetting_state
from tests.utils import testutils

SysVersionInfo = col.namedtuple(
    "VersionInfo", ["major", "minor", "micro", "releaselevel", "serial"]
)
DISPATCHER_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / "dispatcher_functions"
DISPATCHER_STEIN_FUNCTIONS_DIR = (
    testutils.UNIT_TESTS_FOLDER / "dispatcher_functions" / "dispatcher_functions_stein"
)
DISPATCHER_STEIN_INVALID_FUNCTIONS_DIR = (
    testutils.UNIT_TESTS_FOLDER / "broken_functions" / "invalid_stein"
)


class TestDefaultAppSettingsLogs(testutils.AsyncTestCase):
    """Tests for default app settings logs."""

    @classmethod
    def setUpClass(cls):
        cls._ctrl = testutils.start_mockhost(script_root=DISPATCHER_FUNCTIONS_DIR)
        os_environ = os.environ.copy()
        cls._patch_environ = patch.dict("os.environ", os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    async def test_initialize_worker_logging(self):
        """Test if the dispatcher's log can be flushed out during worker
        initialization
        """
        async with self._ctrl as host:
            r = await host.init_worker("3.0.12345")
            self.assertTrue("App Settings state: " in log for log in r.logs)
            self.assertTrue(
                "PYTHON_ENABLE_WORKER_EXTENSIONS: " in log for log in r.logs
            )

    def test_get_python_appsetting_state(self):
        app_setting_state = get_python_appsetting_state()
        expected_string = "PYTHON_ENABLE_WORKER_EXTENSIONS: "
        self.assertIn(expected_string, app_setting_state)


class TestNonDefaultAppSettingsLogs(testutils.AsyncTestCase):
    """Tests for non-default app settings logs."""

    @classmethod
    def setUpClass(cls):
        cls._ctrl = testutils.start_mockhost(script_root=DISPATCHER_FUNCTIONS_DIR)
        os_environ = os.environ.copy()
        os_environ[PYTHON_THREADPOOL_THREAD_COUNT] = "20"
        os_environ[PYTHON_ENABLE_DEBUG_LOGGING] = "1"
        cls._patch_environ = patch.dict("os.environ", os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    async def test_initialize_worker_logging(self):
        """Test if the dispatcher's log can be flushed out during worker
        initialization
        """
        async with self._ctrl as host:
            r = await host.init_worker("3.0.12345")
            self.assertTrue("App Settings state: " in log for log in r.logs)
            self.assertTrue("PYTHON_THREADPOOL_THREAD_COUNT: " in log for log in r.logs)
            self.assertTrue("PYTHON_ENABLE_DEBUG_LOGGING: " in log for log in r.logs)

    def test_get_python_appsetting_state(self):
        app_setting_state = get_python_appsetting_state()
        self.assertIn("PYTHON_THREADPOOL_THREAD_COUNT: 20 | ", app_setting_state)
        self.assertIn("PYTHON_ENABLE_DEBUG_LOGGING: 1 | ", app_setting_state)
        self.assertIn("PYTHON_ENABLE_WORKER_EXTENSIONS: ", app_setting_state)
