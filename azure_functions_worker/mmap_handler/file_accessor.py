# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import Optional
from .memorymappedfile_constants import MemoryMappedFileConstants as consts


class FileAccessor(metaclass=ABCMeta):
    """
    For accessing memory maps.
    This is an interface that must be implemented by sub-classes to provide platform-specific
    support for accessing memory maps.
    Currently the following two sub-classes are implemented:
        1) FileAccessorWindows
        2) FileAccessorUnix
    """
    @abstractmethod
    def open_mem_map(
            self,
            mem_map_name: str,
            mem_map_size: int,
            access: int) -> Optional[mmap.mmap]:
        """
        Opens an existing memory map.
        Returns the opened mmap if successful, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def create_mem_map(self, mem_map_name: str, mem_map_size: int) -> Optional[mmap.mmap]:
        """
        Creates a new memory map.
        Returns the created mmap if successful, None otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def delete_mem_map(self, mem_map_name: str, mem_map: mmap.mmap) -> bool:
        """
        Deletes the memory map and any backing resources associated with it.
        If there is no memory map with the given name, then no action is performed.
        Returns True if the memory map was successfully deleted, False otherwise.
        """
        raise NotImplementedError

    def _is_dirty_bit_set(self, mem_map_name: str, mem_map) -> bool:
        """
        Checks if the dirty bit of the memory map has been set or not.
        This is used to check if a new memory map was created successfully and we don't end up
        using an existing one.
        """
        # The dirty bit is the first byte of the header so seek to the beginning
        mem_map.seek(0)
        # Read the first byte
        byte_read = mem_map.read(1)
        # Check if the dirty bit was set or not
        if byte_read == consts.DIRTY_BIT_SET:
            is_set = True
        else:
            is_set = False
        # Seek back the memory map to the begginging
        mem_map.seek(0)
        return is_set

    def _set_dirty_bit(self, mem_map_name: str, mem_map):
        """
        Sets the dirty bit in the header of the memory map to indicate that this memory map is not
        new anymore.
        """
        # The dirty bit is the first byte of the header so seek to the beginning
        mem_map.seek(0)
        # Set the dirty bit
        mem_map.write(consts.DIRTY_BIT_SET)
        # Seek back the memory map to the begginging
        mem_map.seek(0)