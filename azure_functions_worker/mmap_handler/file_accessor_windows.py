# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import mmap
from typing import Optional
from .file_accessor import FileAccessor


class FileAccessorWindows(FileAccessor):
    """
    For accessing memory maps.
    This implements the FileAccessor interface for Windows.
    """
    def open_mem_map(self, map_name: str, map_size: int , access: int) -> Optional[mmap.mmap]:
        try:
            mmap_ret = mmap.mmap(-1, map_size, map_name, access=access)
            mmap_ret.seek(0)
            return mmap_ret
        except Exception as e:
            # TODO Log Error
            print(e)
            return None

    def create_mem_map(self, map_name: str, map_size: int) -> Optional[mmap.mmap]:
        # Windows also creates the mmap when trying to open it, if it does not already exist.
        mem_map = self.open_mem_map(map_name, map_size, mmap.ACCESS_WRITE)
        if not self._verify_new_map_created(map_name, mem_map):
            raise Exception("Memory map '%s' already exists" % (map_name))
        return mem_map

    def delete_mem_map(self, map_name: str, mmap) -> bool:
        mmap.close()
        return True