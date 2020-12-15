# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import mmap
import os
import struct
from .memorymappedfile_constants import MemoryMappedFileConstants as consts
from .file_accessor_factory import FileAccessorFactory


class FileReader:
    """
    """
    def __init__(self):
        self.file_accessor = FileAccessorFactory.create_file_accessor()

    def _bytes_to_long(self, input_bytes):
        """Decode a set of bytes representing a long.
        This uses the format that C# uses.
        """
        return struct.unpack("<q", input_bytes)[0]

    def _get_content_length(self, map_name):
        """Read the first header from a shared memory.
        These bytes contains the length of the rest of the shared memory.
        TODO throw exceptions in case of failures as opposed to special values like -1.
        """
        try:
            map_content_length = self.file_accessor.open_mmap(
                map_name, consts.CONTENT_HEADER_TOTAL_BYTES, mmap.ACCESS_READ)
        except FileNotFoundError:
            return -1
        if map_content_length is None:
            return -1
        try:
            header_bytes = map_content_length.read(consts.CONTENT_HEADER_TOTAL_BYTES)
            content_length = self._bytes_to_long(header_bytes)
            return content_length
        except ValueError as value_error:
            print("Cannot get content length for memory map '%s': %s" % (map_name, value_error))
            return 0
        finally:
            map_content_length.close()

    def read_content_as_bytes(self, map_name: str, content_offset: int = 0):
        """Read content from a memory mapped file as bytes.
        """
        content_length = self._get_content_length(map_name)
        if content_length < 0:
            return None
        map_length = content_length + consts.CONTENT_HEADER_TOTAL_BYTES
        try:
            map_content = self.file_accessor.open_mmap(map_name, map_length, mmap.ACCESS_READ)
            if map_content is not None:
                try:
                    map_content.seek(consts.CONTENT_HEADER_TOTAL_BYTES)
                    if content_offset > 0:
                        map_content.seek(content_offset, os.SEEK_CUR)
                    content = map_content.read()
                    return content
                except ValueError as value_error:
                    print("Cannot get content for memory map '%s': %s" % (map_name, value_error))
                finally:
                    map_content.close()
        except FileNotFoundError:
            #print("Cannot get content for '%s'" % (map_name))
            pass
        # If we cannot get the content return None
        return None

    def read_content_as_string(self, map_name: str, content_offset: int = 0):
        """Read content from a memory mapped file as a string.
        """
        content_bytes = self.read_content_as_bytes(map_name, content_offset)
        if content_bytes is None:
            return None
        content_str = content_bytes.decode('utf-8')
        return content_str