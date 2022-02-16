# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License
import typing

from tests.stein_tests import testutils
from tests.stein_tests.constants import TIMER_FUNCS_PATH


class TestHttpFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return TIMER_FUNCS_PATH

    def test_timer_past_due(self):
        r = self.webhost.request('GET', 'http_timer_trigger')
        self.assertEqual(r.status_code, 200)

    def check_test_timer_past_due(self, host_out: typing.List[str]):
        self.assertIn('Python timer trigger function ran at', host_out)
