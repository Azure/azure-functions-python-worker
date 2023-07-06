# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time
import typing

from tests.utils import testutils


class TestFixedRetryPolicyFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'retry_policy_functions' / \
                                            'fixed_strategy'

    def test_fixed_retry_policy(self):
        # Checking webhost status.
        time.sleep(5)
        r = self.webhost.request('GET', '', no_prefix=True)
        self.assertTrue(r.ok)

    def check_log_fixed_retry_policy(self, host_out: typing.List[str]):
        self.assertIn('Current retry count: 0', host_out)
        self.assertIn('Current retry count: 1', host_out)
        self.assertIn("Max retries of 3 for function mytimer"
                      " has been reached", host_out)


class TestExponentialRetryPolicyFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'retry_policy_functions' / \
                                            'exponential_strategy'

    def test_retry_policy(self):
        # Checking webhost status.
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=5)
        time.sleep(5)
        self.assertTrue(r.ok)

    def check_log_retry_policy(self, host_out: typing.List[str]):
        self.assertIn('Current retry count: 1', host_out)
        self.assertIn('Current retry count: 2', host_out)
        self.assertIn('Current retry count: 3', host_out)
        self.assertIn("Max retries of 3 for function mytimer"
                      " has been reached", host_out)
