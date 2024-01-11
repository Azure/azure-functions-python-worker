# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
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

INVALID_SCRIPT_FILE_NAME_DIR = testutils.UNIT_TESTS_FOLDER / \
    'file_name_functions' / \
    'invalid_file_name'


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

    def test_default_file_name(self):
        """
        Test the default file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                         PYTHON_SCRIPT_FILE_NAME_DEFAULT)

    def test_return_str_default(self):
        r = self.webhost.request('GET', 'return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello World!')
        self.assertTrue(r.headers['content-type'].startswith('text/plain'))


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

    def test_new_file_name(self):
        """
        Test the new file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                         'test.py')

    def test_return_str_changed(self):
        r = self.webhost.request('GET', 'return_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello World!')
        self.assertTrue(r.headers['content-type'].startswith('text/plain'))


class TestInvalidScriptFileName(testutils.WebHostTestCase):
    """
    Tests for invalid file name
    """

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ[PYTHON_SCRIPT_FILE_NAME] = 'main'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return INVALID_SCRIPT_FILE_NAME_DIR

    def test_invalid_file_name(self):
        """
        Test the invalid file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                         'main')

    def test_return_str_invalid(self):
        r = self.webhost.request('GET', 'return_str')
        self.assertEqual(r.status_code, 500)
