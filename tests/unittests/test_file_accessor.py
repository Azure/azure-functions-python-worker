# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import unittest
from azure_functions_worker import testutils
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryException


class TestFileAccessor(testutils.SharedMemoryTestCase):
    """
    Tests for FileAccessor.
    """
    def test_create_and_delete_mem_map(self):
        """
        Verify if memory maps were created and deleted.
        """
        for mem_map_size in [1, 10, 1024, 2 * 1024 * 1024, 10 * 1024 * 1024]:
            mem_map_name = self.get_new_mem_map_name()
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            self.assertIsNotNone(mem_map)
            delete_status = self.file_accessor.delete_mem_map(mem_map_name,
                                                              mem_map)
            self.assertTrue(delete_status)

    def test_create_mem_map_invalid_inputs(self):
        """
        Attempt to create memory maps with invalid inputs (size and name) and
        verify that an SharedMemoryException is raised.
        """
        mem_map_name = self.get_new_mem_map_name()
        inv_mem_map_size = 0
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid size'):
            self.file_accessor.create_mem_map(mem_map_name, inv_mem_map_size)
        inv_mem_map_name = None
        mem_map_size = 1024
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid name'):
            self.file_accessor.create_mem_map(inv_mem_map_name, mem_map_size)
        inv_mem_map_name = ''
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid name'):
            self.file_accessor.create_mem_map(inv_mem_map_name, mem_map_size)

    def test_open_existing_mem_map(self):
        """
        Verify that an existing memory map can be opened.
        """
        mem_map_size = 1024
        mem_map_name = self.get_new_mem_map_name()
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        o_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNotNone(o_mem_map)
        o_mem_map.close()
        delete_status = self.file_accessor.delete_mem_map(mem_map_name, mem_map)
        self.assertTrue(delete_status)

    def test_open_mem_map_invalid_inputs(self):
        """
        Attempt to open a memory map with invalid inputs (size and name) and
        verify that an SharedMemoryException is raised.
        """
        mem_map_name = self.get_new_mem_map_name()
        inv_mem_map_size = -1
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid size'):
            self.file_accessor.open_mem_map(mem_map_name, inv_mem_map_size)
        inv_mem_map_name = None
        mem_map_size = 1024
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid name'):
            self.file_accessor.open_mem_map(inv_mem_map_name, mem_map_size)
        inv_mem_map_name = ''
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid name'):
            self.file_accessor.open_mem_map(inv_mem_map_name, mem_map_size)

    @unittest.skipIf(os.name == 'nt',
                     'Windows will create an mmap if one does not exist')
    def test_open_deleted_mem_map(self):
        """
        Attempt to open a deleted memory map and verify that it fails.
        Note: Windows creates a new memory map if one does not exist when
              opening a memory map, so we skip this test on Windows.
        """
        mem_map_size = 1024
        mem_map_name = self.get_new_mem_map_name()
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        o_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNotNone(o_mem_map)
        o_mem_map.close()
        delete_status = self.file_accessor.delete_mem_map(mem_map_name, mem_map)
        self.assertTrue(delete_status)
        d_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNone(d_mem_map)
