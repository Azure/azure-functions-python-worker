# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import shutil
import unittest
import uuid
from azure_functions_worker.shared_memory_data_transfer.file_accessor_factory \
    import FileAccessorFactory
from azure_functions_worker.shared_memory_data_transfer. \
    shared_memory_constants import SharedMemoryConstants as consts


class TestFileAccessor(unittest.TestCase):
    def setUp(self):
        self.file_accessor = FileAccessorFactory.create_file_accessor()

    @unittest.skipIf(os.name == 'nt',
                     'Deleting test files applicable only for Unix platform')
    def tearDown(self):
        for temp_dir in consts.UNIX_TEMP_DIRS:
            temp_dir_path = os.path.join(temp_dir, consts.UNIX_TEMP_DIR_SUFFIX)
            shutil.rmtree(temp_dir_path)

    def test_create_and_delete_mem_map(self):
        for mem_map_size in [1, 10, 1024, 2 * 1024 * 1024, 10 * 1024 * 1024]:
            mem_map_name = str(uuid.uuid4())
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            self.assertIsNotNone(mem_map)
            delete_status = self.file_accessor.delete_mem_map(mem_map_name,
                                                              mem_map)
            self.assertTrue(delete_status)

    def test_open_existing_mem_map(self):
        mem_map_size = 1024
        mem_map_name = str(uuid.uuid4())
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        o_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNotNone(o_mem_map)
        o_mem_map.close()
        delete_status = self.file_accessor.delete_mem_map(mem_map_name, mem_map)
        self.assertTrue(delete_status)

    @unittest.skipIf(os.name == 'nt',
                     'Windows will create an mmap if one does not exist')
    def test_open_deleted_mem_map(self):
        mem_map_size = 1024
        mem_map_name = str(uuid.uuid4())
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        o_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNotNone(o_mem_map)
        o_mem_map.close()
        delete_status = self.file_accessor.delete_mem_map(mem_map_name, mem_map)
        self.assertTrue(delete_status)
        d_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNone(d_mem_map)
