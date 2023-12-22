# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

from azure_functions_worker.constants import PYTHON_SCRIPT_FILE_NAME
from tests.utils import testutils

REQUEST_TIMEOUT_SEC = 10


class TestHttpFunctionsFileName(testutils.WebHostTestCase):
    """Test the native Http Trigger in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. Since the Http Trigger is a native suport from host, we
    don't need to setup any external resources.

    Compared to the unittests/test_http_functions.py, this file is more focus
    on testing the E2E flow scenarios.
    """
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein' / \
                                            'file_name'

    @testutils.retryable_test(3, 5)
    def test_index_page_should_return_ok(self):
        """The index page of Azure Functions should return OK in any
        circumstances
        """
        os.environ['PYTHON_SCRIPT_FILE_NAME'] = 'main.py'
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    def test_correct_file_name(self):
        os.environ['PYTHON_SCRIPT_FILE_NAME'] = 'main.py'
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                         'main.py')
