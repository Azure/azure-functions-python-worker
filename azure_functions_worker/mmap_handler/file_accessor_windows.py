# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import mmap
from .file_accessor import FileAccessor


class FileAccessorWindows(FileAccessor):
    def open_mmap(self, map_name: str, map_size: int , access: int = mmap.ACCESS_READ):
        try:
            mmap_ret = mmap.mmap(-1, map_size, map_name, access=access)
            mmap_ret.seek(0)
            return mmap_ret
        except Exception as e:
            # TODO Log Error
            print(e)
            return None

    def create_mmap(self, map_name: str, map_size: int):
        # Windows creates the mmap when trying to open it
        mem_map = self.open_mmap(map_name, map_size, mmap.ACCESS_WRITE)
        if not self._verify_new_map_created(map_name, mem_map):
            raise Exception("Memory map '%s' already exists" % (map_name))
        return mem_map

    def delete_mmap(self, map_name: str, mmap):
        mmap.close()