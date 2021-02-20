# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import math
from azure.functions import meta as bind_meta
from azure_functions_worker import testutils
from azure_functions_worker.shared_memory_data_transfer \
    import SharedMemoryManager
from azure_functions_worker.shared_memory_data_transfer \
    import SharedMemoryConstants as consts


class TestSharedMemoryManager(testutils.SharedMemoryTestCase):
    def test_is_enabled(self):
        pass

    def test_is_disabled(self):
        pass

    def test_bytes_input_support(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        bytes_datum = bind_meta.Datum(type='bytes', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertTrue(is_supported)

    def test_string_input_support(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        bytes_datum = bind_meta.Datum(type='string', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertTrue(is_supported)

    def test_large_invalid_bytes_input_support(self):
        manager = SharedMemoryManager()
        content_size = consts.MAX_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        # Not using get_random_bytes to avoid slowing down for creating a large
        # random input
        content = b'x01' * content_size
        bytes_datum = bind_meta.Datum(type='bytes', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertFalse(is_supported)

    def test_small_invalid_bytes_input_support(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER - 10
        content = self.get_random_bytes(content_size)
        bytes_datum = bind_meta.Datum(type='bytes', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertFalse(is_supported)

    def test_large_invalid_string_input_support(self):
        manager = SharedMemoryManager()
        content_size = consts.MAX_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        # Not using get_random_string to avoid slowing down for creating a large
        # random input
        content = 'a' * num_chars
        string_datum = bind_meta.Datum(type='string', value=content)
        is_supported = manager.is_supported(string_datum)
        self.assertFalse(is_supported)

    def test_small_invalid_string_input_support(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER - 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        string_datum = bind_meta.Datum(type='string', value=content)
        is_supported = manager.is_supported(string_datum)
        self.assertFalse(is_supported)

    def test_put_bytes(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        shared_mem_meta = manager.put_bytes(content)
        self.assertIsNotNone(shared_mem_meta)
        self.assertTrue(self._is_valid_uuid(shared_mem_meta.mem_map_name))
        self.assertEqual(content_size, shared_mem_meta.count)
        free_success = manager.free_mem_map(shared_mem_meta.mem_map_name)
        self.assertTrue(free_success)

    def test_invalid_put_bytes(self):
        manager = SharedMemoryManager()
        shared_mem_meta = manager.put_bytes(None)
        self.assertIsNone(shared_mem_meta)

    def test_get_bytes(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        shared_mem_meta = manager.put_bytes(content)
        mem_map_name = shared_mem_meta.mem_map_name
        num_bytes_written = shared_mem_meta.count
        read_content = manager.get_bytes(mem_map_name, offset=0,
                                         count=num_bytes_written)
        self.assertEqual(content, read_content)
        free_success = manager.free_mem_map(mem_map_name)
        self.assertTrue(free_success)

    def test_put_string(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        expected_size = len(content.encode('utf-8'))
        shared_mem_meta = manager.put_string(content)
        self.assertIsNotNone(shared_mem_meta)
        self.assertTrue(self.is_valid_uuid(shared_mem_meta.mem_map_name))
        self.assertEqual(expected_size, shared_mem_meta.count)
        free_success = manager.free_mem_map(shared_mem_meta.mem_map_name)
        self.assertTrue(free_success)

    def test_invalid_put_string(self):
        manager = SharedMemoryManager()
        shared_mem_meta = manager.put_string(None)
        self.assertIsNone(shared_mem_meta)

    def test_get_string(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        shared_mem_meta = manager.put_string(content)
        mem_map_name = shared_mem_meta.mem_map_name
        num_bytes_written = shared_mem_meta.count
        read_content = manager.get_string(mem_map_name, offset=0,
                                          count=num_bytes_written)
        self.assertEqual(content, read_content)
        free_success = manager.free_mem_map(mem_map_name)
        self.assertTrue(free_success)

    def test_allocated_mem_maps(self):
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        shared_mem_meta = manager.put_bytes(content)
        self.assertIsNotNone(shared_mem_meta)
        mem_map_name = shared_mem_meta.mem_map_name
        is_mem_map_found = mem_map_name in manager.allocated_mem_maps
        self.assertTrue(is_mem_map_found)
        self.assertEqual(1, len(manager.allocated_mem_maps.keys()))
        free_success = manager.free_mem_map(mem_map_name)
        self.assertTrue(free_success)
        is_mem_map_found = mem_map_name in manager.allocated_mem_maps
        self.assertFalse(is_mem_map_found)
        self.assertEqual(0, len(manager.allocated_mem_maps.keys()))

    def test_invalid_put_allocated_mem_maps(self):
        manager = SharedMemoryManager()
        shared_mem_meta = manager.put_bytes(None)
        self.assertIsNone(shared_mem_meta)
        self.assertEqual(0, len(manager.allocated_mem_maps.keys()))

    def test_invalid_free_mem_map(self):
        manager = SharedMemoryManager()
        mem_map_name = self.get_new_mem_map_name()
        free_success = manager.free_mem_map(mem_map_name)
        self.assertFalse(free_success)
