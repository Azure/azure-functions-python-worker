import os
from unittest.mock import patch

from tests.stein_tests import testutils
from tests.stein_tests.constants import UNIT_TESTS_ROOT


class TestLoaderNewPrgModel(testutils.WebHostTestCase):

    function_dir = UNIT_TESTS_ROOT / 'load_functions'

    @classmethod
    def get_script_dir(cls):
        return cls.function_dir

    def test_loader_simple(self):
        r = self.webhost.request('GET', 'hello')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'function_app')
