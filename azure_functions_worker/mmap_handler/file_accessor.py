# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import abc
import mmap


class FileAccessor(metaclass=abc.ABCMeta):
    """
    TODO write docstring.
    """
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'open_mmap') and 
                callable(subclass.load_data_source) and 
                hasattr(subclass, 'create_mmap') and 
                callable(subclass.extract_text) or 
                hasattr(subclass, 'delete_mmap') and 
                callable(subclass.extract_text) or 
                NotImplemented)

    @abc.abstractmethod
    def open_mmap(self, map_name: str, map_size: int , access: int = mmap.ACCESS_READ):
        """Open an existing memory map.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def create_mmap(self, map_name: str, map_size: int):
        """Create a new memory map.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def delete_mmap(self, map_name: str, mmap):
        """Delete a memory map.
        """
        raise NotImplementedError

    def _verify_new_map_created(self, map_name: str, mem_map) -> bool:
        """Checks if the first byte of the memory map is zero.
        If it is not, this memory map already existed.
        """
        mem_map.seek(0)
        byte_read = mem_map.read(1)
        is_new_mmap = False
        if byte_read != b'\x00':
            is_new_mmap = False
        else:
            is_new_mmap = True
        mem_map.seek(0)
        return is_new_mmap