# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

from azure_functions_worker.constants import (
    PYTHON_SCRIPT_FILE_NAME,
    PYTHON_SCRIPT_FILE_NAME_DEFAULT,
)
from tests.utils import testutils

DEFAULT_SCRIPT_FILE_NAME_DIR = (
    testutils.UNIT_TESTS_FOLDER / "file_name_functions" / "default_file_name"
)

NEW_SCRIPT_FILE_NAME_DIR = (
    testutils.UNIT_TESTS_FOLDER / "file_name_functions" / "new_file_name"
)

INVALID_SCRIPT_FILE_NAME_DIR = (
    testutils.UNIT_TESTS_FOLDER / "file_name_functions" / "invalid_file_name"
)


class TestDefaultScriptFileName(testutils.WebHostTestCase):
    """
    Tests for default file name
    """

    @classmethod
    def get_script_name(cls):
        return "function_app.py"

    @classmethod
    def get_script_dir(cls):
        return DEFAULT_SCRIPT_FILE_NAME_DIR

    def test_default_file_name(self):
        """
        Test the default file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(
            os.environ.get(PYTHON_SCRIPT_FILE_NAME), PYTHON_SCRIPT_FILE_NAME_DEFAULT
        )


class TestNewScriptFileName(testutils.WebHostTestCase):
    """
    Tests for changed file name
    """

    @classmethod
    def get_script_dir(cls):
        return NEW_SCRIPT_FILE_NAME_DIR

    @classmethod
    def get_script_name(cls):
        return "test.py"

    def test_new_file_name(self):
        """
        Test the new file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME), "test.py")


class TestInvalidScriptFileName(testutils.WebHostTestCase):
    """
    Tests for invalid file name
    """

    @classmethod
    def get_script_dir(cls):
        return INVALID_SCRIPT_FILE_NAME_DIR

    @classmethod
    def get_script_name(cls):
        return "main"

    def test_invalid_file_name(self):
        """
        Test the invalid file name
        """
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME), "main")
