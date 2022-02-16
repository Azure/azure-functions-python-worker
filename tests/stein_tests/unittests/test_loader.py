import os
from unittest.mock import patch

from tests.stein_tests import testutils


class TestLoaderNewPrgModel(testutils.WebHostTestCase):

    function_dir = testutils.UNIT_TESTS_FOLDER / 'load_functions'

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        # Turn on feature flag
        # os_environ['AzureWebJobsFeatureFlags'] = 'EnableWorkerIndexing'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return cls.function_dir

    def test_loader_simple(self):
        r = self.webhost.request('GET', 'hello')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'function_app')
