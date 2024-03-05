# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import typing

from tests.utils import testutils


class TestWarmupFunctions(testutils.WebHostTestCase):
    """Test the Warmup Trigger in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. This test is more focused on testing e2e scenario for
    warmup trigger function.

    """

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'warmup_functions'

    def test_warmup(self):
        r = self.webhost.request('GET', 'admin/warmup', no_prefix=True)

        self.assertTrue(r.ok)

    def check_log_warmup(self, host_out: typing.List[str]):
        self.assertEqual(host_out.count("Function App instance is warm"), 1)


class TestWarmupFunctionsStein(TestWarmupFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'warmup_functions' / \
                                            'warmup_functions_stein'
