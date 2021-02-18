# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import mmap
import os
import struct
from typing import Optional
from .memorymappedfile_constants import MemoryMappedFileConstants as consts
from .file_accessor_factory import FileAccessorFactory


class FileReader:
    """
    For reading data from memory maps in shared memory.
    Assumes a particular format when reading data (i.e. particular header before the content).
    For writing data that could be read by the FileReader, use FileWriter.
    """
    def __init__(self):
        self.file_accessor = FileAccessorFactory.create_file_accessor()

    def _bytes_to_long(self, input_bytes) -> int:
        """
        Decode a set of bytes representing a long.
        This uses the format that the functions host (i.e. C#) uses.
        """
        return struct.unpack("<q", input_bytes)[0]

    def _get_content_length(self, mem_map_name) -> Optional[int]:
        """
        Read the header of the memory map to determine the length of content contained in that
        memory map.
        Returns the content length as a non-negative integer if successful, None otherwise.
        """
        mem_map_content_length = self.file_accessor.open_mem_map(
            mem_map_name, consts.CONTENT_HEADER_TOTAL_BYTES, mmap.ACCESS_READ)
        if mem_map_content_length is None:
            return None
        try:
            mem_map_content_length.seek(consts.DIRTY_BIT_FLAG_NUM_BYTES)
            header_bytes = mem_map_content_length.read(consts.CONTENT_LENGTH_NUM_BYTES)
            content_length = self._bytes_to_long(header_bytes)
            return content_length
        finally:
            mem_map_content_length.close()

    def read_content_as_bytes(
            self,
            mem_map_name: str,
            content_offset: int = 0,
            bytes_to_read: int = 0) -> Optional[bytes]:
        """
        Read content from the memory map with the given name and starting at the given offset.
        content_offset = 0 means read from the beginning of the content.
        bytes_to_read = 0 means read the entire content.
        Returns the content as bytes if successful, None otherwise.
        """
        content_length = self._get_content_length(mem_map_name)
        if content_length is None:
            return None
        mem_map_size = consts.CONTENT_HEADER_TOTAL_BYTES + content_length
        mem_map_content = self.file_accessor.open_mem_map(mem_map_name, mem_map_size,
            mmap.ACCESS_READ)
        if mem_map_content is None:
            return None
        try:
            mem_map_content.seek(consts.CONTENT_HEADER_TOTAL_BYTES)
            if content_offset > 0:
                mem_map_content.seek(content_offset, os.SEEK_CUR)
            if bytes_to_read > 0:
                # Read up to the specified number of bytes to read
                content = mem_map_content.read(bytes_to_read)
            else:
                # Read the entire content
                content = mem_map_content.read()
            return content
        finally:
            mem_map_content.close()

    def read_content_as_string(
            self,
            mem_map_name: str,
            content_offset: int = 0,
            bytes_to_read: int = 0) -> Optional[str]:
        """
        Read content from the memory map with the given name and starting at the given offset.
        Returns the content as a string if successful, None otherwise.
        """
        content_bytes = self.read_content_as_bytes(mem_map_name, content_offset, bytes_to_read)
        if content_bytes is None:
            return None
        content_str = content_bytes.decode('utf-8')
        return content_str