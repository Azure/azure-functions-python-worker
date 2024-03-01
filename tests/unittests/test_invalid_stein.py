# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import collections as col

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

    async def test_indexing_not_app(self):
        """Test if the functions metadata response will be 0
            when an invalid app is provided
                """
        mock_host = testutils.start_mockhost(
            script_root=STEIN_INVALID_APP_FUNCTIONS_DIR)
        async with mock_host as host:
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertIn("Error", r.response.result.exception.message)

    async def test_indexing_invalid_app(self):
        """Test if the functions metadata response will be 0
            when an invalid app is provided
                """
        mock_host = testutils.start_mockhost(
            script_root=STEIN_INVALID_APP_FUNCTIONS_DIR)
        async with mock_host as host:
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertIn("Error", r.response.result.exception.message)
