# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import re
import sys
import time
import typing

from tests.utils import testutils
from unittest.case import skipIf

REQUEST_TIMEOUT_SEC = 5


@skipIf(sys.version_info.minor >= 10,
        '3.10+ is supported.')
class TestEOLFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'timer_functions'

    def test_timer(self):
        time.sleep(1)
        # Checking webhost status.
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    def check_log_timer(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count("This timer trigger function executed "
                                        "successfully"), 1)
        pattern = r"EOL"

        found = any(re.search(pattern, log) for log in host_out)
        self.assertTrue(found)
