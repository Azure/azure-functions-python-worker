import collections
import os
from unittest.mock import patch

from azure_functions_worker import testutils, protos
from tests.stein_tests.constants import DISPATCHER_FUNCTIONS_DIR

SysVersionInfo = collections.namedtuple("VersionInfo",
                                        ["major", "minor", "micro",
                                         "releaselevel", "serial"])


class TestMetadataRequest(testutils.AsyncTestCase):

    def setUp(self):
        self._ctrl = testutils.start_mockhost(
            script_root=DISPATCHER_FUNCTIONS_DIR)
        self._pre_env = dict(os.environ)
        self.mock_version_info = patch(
            'azure_functions_worker.dispatcher.sys.version_info',
            SysVersionInfo(3, 10, 0, 'final', 0))
        self.mock_version_info.start()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)
        self.mock_version_info.stop()

    async def test_dispatcher_functions_metadata_request(self):
        """Test if the functions metadata response will be sent correctly
        when a functions metadata request is received
        """
        async with self._ctrl as host:
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
