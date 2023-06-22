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
        # Checking webhost status.
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=5)
        self.assertTrue(r.ok)
        time.sleep(1)

    def check_log_retry_policy(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count("Current retry count: 0"), 1)
        self.assertEqual(host_out.count("Current retry count: 1"), 1)
        self.assertEqual(host_out.count(f"Max retries of 1 for function mytimer"
                                        f" has been reached"), 1)

