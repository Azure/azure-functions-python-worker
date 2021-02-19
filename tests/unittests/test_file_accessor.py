# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import unittest
from azure_functions_worker import testutils


class TestFileAccessor(testutils.SharedMemoryTestCase):
    def test_create_and_delete_mem_map(self):
        for mem_map_size in [1, 10, 1024, 2 * 1024 * 1024, 10 * 1024 * 1024]:
            mem_map_name = self.get_new_mem_map_name()
            mem_map = self.file_accessor.create_mem_map(mem_map_name,
                                                        mem_map_size)
            self.assertIsNotNone(mem_map)
            delete_status = self.file_accessor.delete_mem_map(mem_map_name,
                                                              mem_map)
            self.assertTrue(delete_status)

    def test_create_mem_map_invalid_inputs(self):
        mem_map_name = self.get_new_mem_map_name()
        inv_mem_map_size = 0
        with self.assertRaisesRegex(Exception, 'Invalid size'):
            self.file_accessor.create_mem_map(mem_map_name, inv_mem_map_size)
        inv_mem_map_name = None
        mem_map_size = 1024
        with self.assertRaisesRegex(Exception, 'Invalid name'):
            self.file_accessor.create_mem_map(inv_mem_map_name, mem_map_size)
        inv_mem_map_name = ''
        with self.assertRaisesRegex(Exception, 'Invalid name'):
            self.file_accessor.create_mem_map(inv_mem_map_name, mem_map_size)

    def test_open_existing_mem_map(self):
        mem_map_size = 1024
        mem_map_name = self.get_new_mem_map_name()
        mem_map = self.file_accessor.create_mem_map(mem_map_name, mem_map_size)
        o_mem_map = self.file_accessor.open_mem_map(mem_map_name, mem_map_size)
        self.assertIsNotNone(o_mem_map)
        o_mem_map.close()
        delete_status = self.file_accessor.delete_mem_map(mem_map_name, mem_map)
        self.assertTrue(delete_status)

    def test_open_mem_map_invalid_inputs(self):
        mem_map_name = self.get_new_mem_map_name()
        inv_mem_map_size = -1
        with self.assertRaisesRegex(Exception, 'Invalid size'):
            self.file_accessor.open_mem_map(mem_map_name, inv_mem_map_size)
        inv_mem_map_name = None
        mem_map_size = 1024
        with self.assertRaisesRegex(Exception, 'Invalid name'):
            self.file_accessor.open_mem_map(inv_mem_map_name, mem_map_size)
        inv_mem_map_name = ''
        with self.assertRaisesRegex(Exception, 'Invalid name'):
            self.file_accessor.open_mem_map(inv_mem_map_name, mem_map_size)

    @unittest.skipIf(os.name == 'nt',
                     'Windows will create an mmap if one does not exist')
    def test_open_deleted_mem_map(self):
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
