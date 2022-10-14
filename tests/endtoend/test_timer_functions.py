# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import time
import typing
from unittest.mock import patch
from tests.utils import testutils
import requests

REQUEST_TIMEOUT_SEC = 5


class TestTimerFunctions(testutils.WebHostTestCase):
    """Test the Timer in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. Since the Timer Trigger is a native support from host, we
    don't need to setup any external resources.

    Compared to the unittests/test_http_functions.py, this file is more focus
    on testing the E2E flow scenarios.
    """

    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_environ.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'timer_functions'

    def test_timer(self):
        time.sleep(6)
        root_url = self.webhost._addr
        r = requests.get(root_url, timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    def check_log_timer(self, host_out: typing.List[str]):
        self.assertIn('This timer trigger function executed successfully',
                      host_out)
        self.assertEqual(host_out.count("This timer trigger function executed "
                                        "successfully"), 3)


class TestTimerFunctionsStein(TestTimerFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'timer_functions' / \
                                            'timer_functions_stein'
