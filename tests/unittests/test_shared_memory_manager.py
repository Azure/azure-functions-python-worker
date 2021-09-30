# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import math
import os
import json
import sys
from unittest.mock import patch
from azure_functions_worker.utils.common import is_envvar_true
from azure.functions import meta as bind_meta
from azure_functions_worker import testutils
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryManager
from azure_functions_worker.bindings.shared_memory_data_transfer \
    import SharedMemoryConstants as consts
from azure_functions_worker.constants \
    import FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED


class TestSharedMemoryManager(testutils.SharedMemoryTestCase):
    """
    Tests for SharedMemoryManager.
    """
    def setUp(self):
        self.mock_environ = patch.dict('os.environ', os.environ.copy())
        self.mock_sys_module = patch.dict('sys.modules', sys.modules.copy())
        self.mock_sys_path = patch('sys.path', sys.path.copy())
        self.mock_environ.start()
        self.mock_sys_module.start()
        self.mock_sys_path.start()

    def tearDown(self):
        self.mock_sys_path.stop()
        self.mock_sys_module.stop()
        self.mock_environ.stop()

    def test_is_enabled(self):
        """
        Verify that when the AppSetting is enabled, SharedMemoryManager is
        enabled.
        """

        # Make sure shared memory data transfer is enabled
        was_shmem_env_true = is_envvar_true(
            FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED)
        os.environ.update(
            {FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED: '1'})
        manager = SharedMemoryManager()
        self.assertTrue(manager.is_enabled())
        # Restore the env variable to original value
        if not was_shmem_env_true:
            os.environ.update(
                {FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED: '0'})

    def test_is_disabled(self):
        """
        Verify that when the AppSetting is disabled, SharedMemoryManager is
        disabled.
        """
        # Make sure shared memory data transfer is disabled
        was_shmem_env_true = is_envvar_true(
            FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED)
        os.environ.update(
            {FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED: '0'})
        manager = SharedMemoryManager()
        self.assertFalse(manager.is_enabled())
        # Restore the env variable to original value
        if was_shmem_env_true:
            os.environ.update(
                {FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED: '1'})

    def test_bytes_input_support(self):
        """
        Verify that the given input is supported by SharedMemoryManager to be
        transfered over shared memory.
        The input is bytes.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        bytes_datum = bind_meta.Datum(type='bytes', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertTrue(is_supported)

    def test_string_input_support(self):
        """
        Verify that the given input is supported by SharedMemoryManager to be
        transfered over shared memory.
        The input is string.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        bytes_datum = bind_meta.Datum(type='string', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertTrue(is_supported)

    def test_int_input_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is int.
        """
        manager = SharedMemoryManager()
        datum = bind_meta.Datum(type='int', value=1)
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_double_input_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is double.
        """
        manager = SharedMemoryManager()
        datum = bind_meta.Datum(type='double', value=1.0)
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_json_input_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is json.
        """
        manager = SharedMemoryManager()
        content = {
            'name': 'foo',
            'val': 'bar'
        }
        datum = bind_meta.Datum(type='json', value=json.dumps(content))
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_collection_string_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is collection_string.
        """
        manager = SharedMemoryManager()
        content = ['foo', 'bar']
        datum = bind_meta.Datum(type='collection_string', value=content)
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_collection_bytes_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is collection_bytes.
        """
        manager = SharedMemoryManager()
        content = [b'x01', b'x02']
        datum = bind_meta.Datum(type='collection_bytes', value=content)
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_collection_double_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is collection_double.
        """
        manager = SharedMemoryManager()
        content = [1.0, 2.0]
        datum = bind_meta.Datum(type='collection_double', value=content)
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_collection_sint64_unsupported(self):
        """
        Verify that the given input is unsupported by SharedMemoryManager.
        This input is collection_sint64.
        """
        manager = SharedMemoryManager()
        content = [1, 2]
        datum = bind_meta.Datum(type='collection_sint64', value=content)
        is_supported = manager.is_supported(datum)
        self.assertFalse(is_supported)

    def test_large_invalid_bytes_input_support(self):
        """
        Verify that the given input is NOT supported by SharedMemoryManager to
        be transfered over shared memory.
        The input is bytes of larger than the allowed size.
        """
        manager = SharedMemoryManager()
        content_size = consts.MAX_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        # Not using get_random_bytes to avoid slowing down for creating a large
        # random input
        content = b'x01' * content_size
        bytes_datum = bind_meta.Datum(type='bytes', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertFalse(is_supported)

    def test_small_invalid_bytes_input_support(self):
        """
        Verify that the given input is NOT supported by SharedMemoryManager to
        be transfered over shared memory.
        The input is bytes of smaller than the allowed size.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER - 10
        content = self.get_random_bytes(content_size)
        bytes_datum = bind_meta.Datum(type='bytes', value=content)
        is_supported = manager.is_supported(bytes_datum)
        self.assertFalse(is_supported)

    def test_large_invalid_string_input_support(self):
        """
        Verify that the given input is NOT supported by SharedMemoryManager to
        be transfered over shared memory.
        The input is string of larger than the allowed size.
        """
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
        """
        Verify that the given input is NOT supported by SharedMemoryManager to
        be transfered over shared memory.
        The input is string of smaller than the allowed size.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER - 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        string_datum = bind_meta.Datum(type='string', value=content)
        is_supported = manager.is_supported(string_datum)
        self.assertFalse(is_supported)

    def test_put_bytes(self):
        """
        Verify that the given input was successfully put into shared memory.
        The input is bytes.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        shared_mem_meta = manager.put_bytes(content)
        self.assertIsNotNone(shared_mem_meta)
        self.assertTrue(self.is_valid_uuid(shared_mem_meta.mem_map_name))
        self.assertEqual(content_size, shared_mem_meta.count_bytes)
        free_success = manager.free_mem_map(shared_mem_meta.mem_map_name)
        self.assertTrue(free_success)

    def test_invalid_put_bytes(self):
        """
        Attempt to put bytes using an invalid input and verify that it fails.
        """
        manager = SharedMemoryManager()
        shared_mem_meta = manager.put_bytes(None)
        self.assertIsNone(shared_mem_meta)

    def test_get_bytes(self):
        """
        Verify that the output object was successfully gotten from shared
        memory.
        The output is bytes.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        content = self.get_random_bytes(content_size)
        shared_mem_meta = manager.put_bytes(content)
        mem_map_name = shared_mem_meta.mem_map_name
        num_bytes_written = shared_mem_meta.count_bytes
        read_content = manager.get_bytes(mem_map_name, offset=0,
                                         count=num_bytes_written)
        self.assertEqual(content, read_content)
        free_success = manager.free_mem_map(mem_map_name)
        self.assertTrue(free_success)

    def test_put_string(self):
        """
        Verify that the given input was successfully put into shared memory.
        The input is string.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        expected_size = len(content.encode('utf-8'))
        shared_mem_meta = manager.put_string(content)
        self.assertIsNotNone(shared_mem_meta)
        self.assertTrue(self.is_valid_uuid(shared_mem_meta.mem_map_name))
        self.assertEqual(expected_size, shared_mem_meta.count_bytes)
        free_success = manager.free_mem_map(shared_mem_meta.mem_map_name)
        self.assertTrue(free_success)

    def test_invalid_put_string(self):
        """
        Attempt to put a string using an invalid input and verify that it fails.
        """
        manager = SharedMemoryManager()
        shared_mem_meta = manager.put_string(None)
        self.assertIsNone(shared_mem_meta)

    def test_get_string(self):
        """
        Verify that the output object was successfully gotten from shared
        memory.
        The output is string.
        """
        manager = SharedMemoryManager()
        content_size = consts.MIN_BYTES_FOR_SHARED_MEM_TRANSFER + 10
        num_chars = math.floor(content_size / consts.SIZE_OF_CHAR_BYTES)
        content = self.get_random_string(num_chars)
        shared_mem_meta = manager.put_string(content)
        mem_map_name = shared_mem_meta.mem_map_name
        num_bytes_written = shared_mem_meta.count_bytes
        read_content = manager.get_string(mem_map_name, offset=0,
                                          count=num_bytes_written)
        self.assertEqual(content, read_content)
        free_success = manager.free_mem_map(mem_map_name)
        self.assertTrue(free_success)

    def test_allocated_mem_maps(self):
        """
        Verify that the SharedMemoryManager is tracking the shared memory maps
        it has allocated after put operations.
        Verify that those shared memory maps are freed and no longer tracked
        after attempting to free them.
        """
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
        """
        Verify that after an invalid put operation, no shared memory maps were
        added to the list of allocated/tracked shared memory maps.
        i.e. no resources were leaked for invalid operations.
        """
        manager = SharedMemoryManager()
        shared_mem_meta = manager.put_bytes(None)
        self.assertIsNone(shared_mem_meta)
        self.assertEqual(0, len(manager.allocated_mem_maps.keys()))

    def test_invalid_free_mem_map(self):
        """
        Attempt to free a shared memory map that does not exist in the list of
        allocated/tracked shared memory maps and verify that it fails.
        """
        manager = SharedMemoryManager()
        mem_map_name = self.get_new_mem_map_name()
        free_success = manager.free_mem_map(mem_map_name)
        self.assertFalse(free_success)
