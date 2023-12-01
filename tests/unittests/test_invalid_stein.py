# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import collections as col
import os
from unittest.mock import patch

from azure_functions_worker import protos
from tests.utils import testutils

SysVersionInfo = col.namedtuple("VersionInfo", ["major", "minor", "micro",
                                                "releaselevel", "serial"])
STEIN_INVALID_APP_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / \
    'broken_functions' / \
    'invalid_app_stein'
STEIN_INVALID_FUNCTIONS_DIR = testutils.UNIT_TESTS_FOLDER / \
    'broken_functions' / \
    'invalid_stein'


class TestInvalidAppStein(testutils.AsyncTestCase):

    def setUp(self):
        self._ctrl = testutils.start_mockhost(
            script_root=STEIN_INVALID_APP_FUNCTIONS_DIR)
        self._pre_env = dict(os.environ)
        self.mock_version_info = patch(
            'azure_functions_worker.dispatcher.sys.version_info',
            SysVersionInfo(3, 9, 0, 'final', 0))
        self.mock_version_info.start()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_indexing_not_app(self):
        """Test if the functions metadata response will be 0
            when an invalid app is provided
                """
        async with self._ctrl as host:
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertIn("Error", r.response.result.exception.message)


class TestInvalidStein(testutils.AsyncTestCase):

    def setUp(self):
        self._ctrl = testutils.start_mockhost(
            script_root=STEIN_INVALID_FUNCTIONS_DIR)
        self._pre_env = dict(os.environ)
        self.mock_version_info = patch(
            'azure_functions_worker.dispatcher.sys.version_info',
            SysVersionInfo(3, 9, 0, 'final', 0))
        self.mock_version_info.start()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_indexing_invalid_app(self):
        """Test if the functions metadata response will be 0
            when an invalid app is provided
                """
        async with self._ctrl as host:
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertIn("Error", r.response.result.exception.message)
