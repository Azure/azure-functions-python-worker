# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import unittest
from azure_functions_worker.shared_memory_data_transfer.file_accessor_factory \
    import FileAccessorFactory
from azure_functions_worker.shared_memory_data_transfer.file_accessor_unix \
    import FileAccessorUnix
from azure_functions_worker.shared_memory_data_transfer.file_accessor_windows \
    import FileAccessorWindows


class TestFileAccessorFactory(unittest.TestCase):
    def test_proper_subclass_generated(self):
        file_accessor = FileAccessorFactory.create_file_accessor()
        if os.name == 'nt':
            self.assertTrue(type(file_accessor) is FileAccessorWindows)
        else:
            self.assertTrue(type(file_accessor) is FileAccessorUnix)
