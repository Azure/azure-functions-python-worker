# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import unittest
from azure_functions_worker import testutils
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryMap
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryConstants as consts
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryException


class TestSharedMemoryMap(testutils.SharedMemoryTestCase):
    """
    Tests for SharedMemoryMap.
    """
    def test_init(self):
        """
        Verify the initialization of a SharedMemoryMap.
        """
        mem_map_name = self.get_new_mem_map_name()
        mem_map_size = 1024
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                         mem_map)
        self.assertIsNotNone(shared_mem_map)
        dispose_status = shared_mem_map.dispose()
        self.assertTrue(dispose_status)

    def test_init_with_invalid_inputs(self):
        """
        Attempt to initialize a SharedMemoryMap from invalid inputs (name and
        mmap) and verify that an SharedMemoryException is raised.
        """
        inv_mem_map_name = None
        mem_map_name = self.get_new_mem_map_name()
        mem_map_size = 1024
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid name'):
            SharedMemoryMap(self.file_accessor, inv_mem_map_name, mem_map)
        inv_mem_map_name = ''
        with self.assertRaisesRegex(SharedMemoryException, 'Invalid name'):
            SharedMemoryMap(self.file_accessor, inv_mem_map_name, mem_map)
        with self.assertRaisesRegex(SharedMemoryException,
                                    'Invalid memory map'):
            SharedMemoryMap(self.file_accessor, mem_map_name, None)

    def test_put_bytes(self):
        """
        Create a SharedMemoryMap and write bytes to it.
        """
        for content_size in [1, 10, 1024, 2 * 1024 * 1024, 20 * 1024 * 1024]:
            mem_map_name = self.get_new_mem_map_name()
            mem_map_size = content_size + consts.CONTENT_HEADER_TOTAL_BYTES
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                             mem_map)
            content = self.get_random_bytes(content_size)
            num_bytes_written = shared_mem_map.put_bytes(content)
            self.assertEqual(content_size, num_bytes_written)
            dispose_status = shared_mem_map.dispose()
            self.assertTrue(dispose_status)

    def test_get_bytes(self):
        """
        Create a SharedMemoryMap, write bytes to it and then read them back.
        Verify that the bytes written and read match.
        """
        for content_size in [1, 10, 1024, 2 * 1024 * 1024, 20 * 1024 * 1024]:
            mem_map_name = self.get_new_mem_map_name()
            mem_map_size = content_size + consts.CONTENT_HEADER_TOTAL_BYTES
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                             mem_map)
            content = self.get_random_bytes(content_size)
            num_bytes_written = shared_mem_map.put_bytes(content)
            self.assertEqual(content_size, num_bytes_written)
            read_content = shared_mem_map.get_bytes()
            self.assertEqual(content, read_content)
            dispose_status = shared_mem_map.dispose()
            self.assertTrue(dispose_status)

    def test_put_bytes_more_than_capacity(self):
        """
        Attempt to put more bytes into the created SharedMemoryMap than the
        size with which it was created. Verify that an SharedMemoryException is
        raised.
        """
        mem_map_name = self.get_new_mem_map_name()
        mem_map_size = 1024 + consts.CONTENT_HEADER_TOTAL_BYTES
        mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                    mem_map_size)
        shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                         mem_map)
        # Attempt to write more bytes than the size of the memory map we created
        # earlier (1024).
        content_size = 2048
        content = self.get_random_bytes(content_size)
        with self.assertRaisesRegex(ValueError, 'out of range'):
            shared_mem_map.put_bytes(content)
        dispose_status = shared_mem_map.dispose()
        self.assertTrue(dispose_status)

    @unittest.skipIf(os.name == 'nt',
                     'Windows will create an mmap if one does not exist')
    def test_dispose_without_delete_file(self):
        """
        Dispose a SharedMemoryMap without making it dispose the backing file
        resources (on Unix). Verify that the same memory map can be opened again
        as the backing file was still present.
        """
        mem_map_name = self.get_new_mem_map_name()
        mem_map_size = 1024 + consts.CONTENT_HEADER_TOTAL_BYTES
        mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                    mem_map_size)
        shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                         mem_map)
        # Close the memory map but do not delete the backing file
        dispose_status = shared_mem_map.dispose(is_delete_file=False)
        self.assertTrue(dispose_status)
        # Attempt to open the memory map again, it should still open since the
        # backing file is present
        mem_map_op = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNotNone(mem_map_op)
        delete_status = \
            self.file_accessor.delete_mem_map(mem_map_name, mem_map_op)
        self.assertTrue(delete_status)
