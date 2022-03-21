# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import sys
import unittest
from unittest.mock import patch

from azure_functions_worker.bindings.shared_memory_data_transfer import (
    FileAccessorFactory,
)
from azure_functions_worker.bindings.shared_memory_data_transfer.file_accessor_unix import (
    FileAccessorUnix,
)
from azure_functions_worker.bindings.shared_memory_data_transfer.file_accessor_windows import (
    FileAccessorWindows,
)


class TestFileAccessorFactory(unittest.TestCase):
    """
    Tests for FileAccessorFactory.
    """

    def setUp(self):
        env = os.environ.copy()
        env["FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED"] = "true"
        self.mock_environ = patch.dict("os.environ", env)
        self.mock_environ.start()

    def tearDown(self):
        self.mock_environ.stop()

    @unittest.skipIf(
        os.name != "nt", "FileAccessorWindows is only valid on Windows"
    )
    def test_file_accessor_windows_created(self):
        """
        Verify that FileAccessorWindows was created when running on Windows.
        """
        file_accessor = FileAccessorFactory.create_file_accessor()
        self.assertTrue(type(file_accessor) is FileAccessorWindows)

    @unittest.skipIf(
        os.name == "nt" or sys.platform == "darwin",
        "FileAccessorUnix is only valid on Unix",
    )
    def test_file_accessor_unix_created(self):
        """
        Verify that FileAccessorUnix was created when running on Windows.
        """
        file_accessor = FileAccessorFactory.create_file_accessor()
        self.assertTrue(type(file_accessor) is FileAccessorUnix)
