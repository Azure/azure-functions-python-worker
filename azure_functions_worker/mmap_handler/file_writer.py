# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import mmap
from typing import Optional
from typing import Union
from .file_accessor_factory import FileAccessorFactory
from .memorymappedfile_constants import MemoryMappedFileConstants as consts


class FileWriter:
    """
    """
    def __init__(self):
        self.file_accessor = FileAccessorFactory.create_file_accessor()

    def create_with_content_bytes(self, map_name: str, content: bytes) -> Optional[mmap.mmap]:
        if content is None:
            return None
        content_size = len(content)
        map_size = consts.CONTENT_HEADER_TOTAL_BYTES + content_size
        mem_map = self.file_accessor.create_mmap(map_name, map_size)
        content_size_bytes = content_size.to_bytes(consts.CONTENT_LENGTH_NUM_BYTES, byteorder=sys.byteorder)
        mem_map.write(content_size_bytes)
        mem_map.write(content)
        mem_map.flush()
        return mem_map

    def create_with_content_string(self, map_name: str, content: str) -> Optional[mmap.mmap]:
        if content is None:
            return None
        content_bytes = content.encode('utf-8')
        return self.create_with_content_bytes(map_name, content_bytes)
