# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from azure_functions_worker import testutils
from azure_functions_worker.shared_memory_data_transfer.shared_memory_map \
    import SharedMemoryMap
from azure_functions_worker.shared_memory_data_transfer. \
    shared_memory_constants import SharedMemoryConstants as consts


class TestSharedMemoryMap(testutils.SharedMemoryTestCase):
    def test_init(self):
        mem_map_name = self.get_new_mem_map_name()
        mem_map_size = 1024
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        shared_mem_map = SharedMemoryMap(self.file_accessor, mem_map_name,
                                         mem_map)
        self.assertIsNotNone(shared_mem_map)
        dispose_status = shared_mem_map.dispose()
        self.assertTrue(dispose_status)

    def test_init_with_invalid_inputs(self):
        inv_mem_map_name = None
        mem_map_name = self.get_new_mem_map_name()
        mem_map_size = 1024
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        with self.assertRaisesRegex(Exception, 'Invalid name'):
            SharedMemoryMap(self.file_accessor, inv_mem_map_name, mem_map)
        inv_mem_map_name = ''
        with self.assertRaisesRegex(Exception, 'Invalid name'):
            SharedMemoryMap(self.file_accessor, inv_mem_map_name, mem_map)
        with self.assertRaisesRegex(Exception, 'Invalid memory map'):
            SharedMemoryMap(self.file_accessor, mem_map_name, None)

    def test_put_bytes(self):
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
        pass

    def test_dispose_without_delete_file(self):
        pass