# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time
import typing

from tests.utils import testutils


class TestRetryPolicyFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'retry_policy_functions'

    def test_retry_policy(self):
        time.sleep(1)
        # Checking webhost status.
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=5)
        self.assertTrue(r.ok)

    def check_log_retry_policy(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count("Current retry count:"), 3)

