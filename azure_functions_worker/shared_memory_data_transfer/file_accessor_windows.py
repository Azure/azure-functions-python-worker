# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from __future__ import annotations
import mmap
from typing import Optional
from .file_accessor import FileAccessor
from ..logging import logger


class FileAccessorWindows(FileAccessor):
    """
    For accessing memory maps.
    This implements the FileAccessor interface for Windows.
    """
    def open_mem_map(
            self,
            mem_map_name: str,
            mem_map_size: int,
            access: int = mmap.ACCESS_READ) -> Optional[mmap.mmap]:
        try:
            mmap_ret = mmap.mmap(-1, mem_map_size, mem_map_name, access=access)
            return mmap_ret
        except Exception as e:
            logger.warn(f'Cannot open memory map {mem_map_name} with size {mem_map_size} - {e}')
            return None

    def create_mem_map(self, mem_map_name: str, mem_map_size: int) -> Optional[mmap.mmap]:
        # Windows also creates the mmap when trying to open it, if it does not already exist.
        mem_map = self.open_mem_map(mem_map_name, mem_map_size, mmap.ACCESS_WRITE)
        if mem_map is None:
            return None
        if self._is_mem_map_initialized(mem_map):
            raise Exception(f'Cannot create memory map {mem_map_name} as it already exists')
        self._set_mem_map_initialized(mem_map)
        return mem_map

    def delete_mem_map(self, mem_map_name: str, mmap) -> bool:
        mmap.close()
        return True
