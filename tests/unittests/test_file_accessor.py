# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import unittest
import uuid
from azure_functions_worker.shared_memory_data_transfer.file_accessor_factory import FileAccessorFactory


class TestFileAccessor(unittest.TestCase):
    def setUp(self):
        self.file_accessor = FileAccessorFactory.create_file_accessor()

    def test_init_shared_memory_map(self):
        mem_map_name = str(uuid.uuid4())
        content_size = 2 * 1024 * 1024 # 2 MB
        mem_map = self.file_accessor.create_mem_map(mem_map_name, content_size)
        assert mem_map is not None