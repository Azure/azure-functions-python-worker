# -*- coding: utf-8 -*-

import sys
import mmap
from typing import Optional
from typing import Union
from .file_accessor import FileAccessor
from .memorymappedfile_constants import MemoryMappedFileConstants as consts
from .memorymappedfile_controlflags import MemoryMappedFileControlFlags as flags


class FileWriter:
    @staticmethod
    def create_with_content_bytes(map_name: str, content: bytes) -> Optional[mmap.mmap]:
        if content is None:
            return None
        content_size = len(content)
        map_size = consts.CONTENT_HEADER_TOTAL_BYTES + content_size
        mem_map = FileAccessor.create_mmap(map_name, map_size)
        # Skip the first byte as it will be written at the end, when the rest of the content is ready
        mem_map.seek(consts.CONTROL_FLAG_NUM_BYTES)
        content_size_bytes = content_size.to_bytes(consts.CONTENT_LENGTH_NUM_BYTES, byteorder=sys.byteorder)
        mem_map.write(content_size_bytes)
        mem_map.write(content)
        mem_map.seek(0)
        flag_bytes = bytes([flags.READY_TO_READ.value])
        mem_map.write(flag_bytes)
        mem_map.flush()
        return mem_map

    @staticmethod
    def create_with_content_string(map_name: str, content: str) -> Optional[mmap.mmap]:
        if content is None:
            return None
        content_bytes = content.encode('utf-8')
        return FileWriter.create_with_content_bytes(map_name, content_bytes)
