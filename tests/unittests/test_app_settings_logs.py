# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import collections as col
import os

from unittest.mock import patch

from tests.utils import testutils
from azure_functions_worker.constants import PYTHON_THREADPOOL_THREAD_COUNT, \
    PYTHON_ENABLE_DEBUG_LOGGING

SysVersionInfo = col.namedtuple("VersionInfo", ["major", "minor", "micro",
                                                "releaselevel", "serial"])
DISPATCHER_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / 'dispatcher_functions'
DISPATCHER_STEIN_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / \
    'dispatcher_functions' / \
    'dispatcher_functions_stein'
DISPATCHER_STEIN_INVALID_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / \
    'broken_functions' / \
    'invalid_stein'


class TestDefaultAppSettingsLogs(testutils.AsyncTestCase):
    """Tests for default app settings logs."""

    @classmethod
    def setUpClass(self):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_FUNCTIONS_DIR)
        os_environ = os.environ.copy()
        self._patch_environ = patch.dict('os.environ', os_environ)
        self._patch_environ.start()
        super().setUpClass()

    def tearDownClass(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_initialize_worker_logging(self):
        """Test if the dispatcher's log can be flushed out during worker
        initialization
        """
        async with self._ctrl as host:
            r = await host.init_worker('3.0.12345')
            self.assertEqual(
                len([log for log in r.logs if log.message.contains(
                    'App Settings state:'
                )]), 1
            )
            self.assertEqual(
                len([log for log in r.logs if log.message.contains(
                    'PYTHON_ENABLE_WORKER_EXTENSIONS:'
                )]), 1
            )
            self.assertEqual(
                len([log for log in r.logs if log.message.contains(
                    'PYTHON_ENABLE_DEBUG_LOGGING:'
                )]), 0
            )


class TestNonDefaultAppSettingsLogs(testutils.AsyncTestCase):
    """Tests for non-default app settings logs."""

    @classmethod
    def setUpClass(self):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_FUNCTIONS_DIR)
        os_environ = os.environ.copy()
        os_environ[PYTHON_THREADPOOL_THREAD_COUNT] = '20'
        os_environ[PYTHON_ENABLE_DEBUG_LOGGING] = '1'
        self._patch_environ = patch.dict('os.environ', os_environ)
        self._patch_environ.start()
        super().setUpClass()

    def tearDownClass(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_initialize_worker_logging(self):
        """Test if the dispatcher's log can be flushed out during worker
        initialization
        """
        async with self._ctrl as host:
            r = await host.init_worker('3.0.12345')
            self.assertEqual(
                len([log for log in r.logs if log.message.contains(
                    'App Settings state:'
                )]), 1
            )
            self.assertEqual(
                len([log for log in r.logs if log.message.contains(
                    'PYTHON_THREADPOOL_THREAD_COUNT:'
                )]), 1
            )
            self.assertEqual(
                len([log for log in r.logs if log.message.contains(
                    'PYTHON_ENABLE_DEBUG_LOGGING:'
                )]), 1
            )
