# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import collections as col
import os
from unittest.mock import patch

from tests.utils import testutils
from azure_functions_worker.constants import \
    PYTHON_SCRIPT_FILE_NAME, PYTHON_SCRIPT_FILE_NAME_DEFAULT

DEFAULT_SCRIPT_FILE_NAME_DIR = testutils.UNIT_TESTS_FOLDER / \
    'file_name_functions' / \
    'default_file_name'

NEW_SCRIPT_FILE_NAME_DIR = testutils.UNIT_TESTS_FOLDER / \
    'file_name_functions' / \
    'new_file_name'

class TestDefaultScriptFileName(testutils.WebHostTestCase):
    """
    Tests for default file name
    """

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ[PYTHON_SCRIPT_FILE_NAME] = PYTHON_SCRIPT_FILE_NAME_DEFAULT
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return DEFAULT_SCRIPT_FILE_NAME_DIR

    async def test_dispatcher_default_file_name(self):
        """
        Test the default file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                         PYTHON_SCRIPT_FILE_NAME_DEFAULT)


class TestNewScriptFileName(testutils.WebHostTestCase):
        """
        Tests for changed file name
        """

        @classmethod
        def setUpClass(cls):
            os_environ = os.environ.copy()
            os_environ[PYTHON_SCRIPT_FILE_NAME] = 'test.py'
            cls._patch_environ = patch.dict('os.environ', os_environ)
            cls._patch_environ.start()
            super().setUpClass()

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()
            cls._patch_environ.stop()

        @classmethod
        def get_script_dir(cls):
            return NEW_SCRIPT_FILE_NAME_DIR

        async def test_dispatcher_new_file_name(self):
            """
            Test the new file name
            """
            self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
            self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                             'test.py')

