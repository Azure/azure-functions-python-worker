# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from __future__ import annotations
import uuid
from typing import Dict, Optional
from ..logging import logger
from ..mmap_handler.file_writer import FileWriter
from ..mmap_handler.file_reader import FileReader
from ..mmap_handler.file_accessor_factory import FileAccessorFactory
from ..utils.common import is_envvar_true
from ..constants import FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED


class SharedMemoryManager:
    """
    Performs all operations related to reading/writing data from/to shared memory.
    This is used for transferring input/output data of the function from/to the functions host over
    shared memory as opposed to RPC to improve the rate of data transfer and the function's
    end-to-end latency.
    """
    def __init__(self):
        # The allocated memory maps are tracked here so that a reference to them is kept open until
        # they have been used (e.g. if they contain a function's output, it is read by the
        # functions host).
        # Having a mapping of the name and the memory map is then later used to close a given
        # memory map by its name, after it has been used.
        # key: mem_map_name, val: mmap.mmap
        self.allocated_mem_maps: Dict[str, mmap.mmap] = {}
        self.file_accessor = FileAccessorFactory.create_file_accessor()
        self.file_reader = FileReader()
        self.file_writer = FileWriter()

    def is_enabled(self) -> bool:
        """
        Whether supported types should be transferred between functions host and the worker using
        shared memory.
        """
        return is_envvar_true(FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED)

    def is_supported(self, datum: Datum) -> bool:
        """
        Whether the given Datum object can be transferred to the functions host using shared
        memory.
        """
        if datum.type == 'bytes':
            # TODO gochaudh: Check for min size config
            # Is there a common place to put configs shared b/w host and worker?
            # Env variable? App Setting?
            return True
        elif datum.type == 'string':
            return True
        return False

    def get_bytes(self, mem_map_name: str, offset: int, count: int) -> Optional[bytes]:
        """
        Reads data from the given memory map with the provided name, starting at the provided
        offset and reading a total of count bytes.
        Returns the data read from shared memory as bytes if successful, None otherwise.
        """
        data = self.file_reader.read_content_as_bytes(mem_map_name, offset, count)
        return data

    def get_string(self, mem_map_name: str, offset: int, count: int) -> Optional[str]:
        """
        Reads data from the given memory map with the provided name, starting at the provided
        offset and reading a total of count bytes.
        Returns the data read from shared memory as a string if successful, None otherwise.
        """
        data = self.file_reader.read_content_as_string(mem_map_name, offset, count)
        return data

    def put_bytes(self, data: bytes) -> Optional[str]:
        """
        Writes the given bytes into shared memory.
        Returns the name of the memory map into which the data was written if successful, None
        otherwise.
        """
        mem_map_name = str(uuid.uuid4())
        mem_map = self.file_writer.create_with_content_bytes(mem_map_name, data)
        if mem_map is None:
            return None
        self.allocated_mem_maps[mem_map_name] = mem_map
        return mem_map_name

    def put_string(self, data: str) -> Optional[str]:
        """
        Writes the given string into shared memory.
        Returns the name of the memory map into which the data was written if succesful, None
        otherwise.
        """
        mem_map_name = str(uuid.uuid4())
        mem_map = self.file_writer.create_with_content_string(mem_map_name, data)
        if mem_map is None:
            return None
        self.allocated_mem_maps[mem_map_name] = mem_map
        return mem_map_name

    def free_mem_map(self, mem_map_name: str):
        """
        Frees the memory map and any backing resources (e.g. file in the case of Unix) associated
        with it.
        If there is no memory map with the given name being tracked, then no action is performed.
        Returns True if the memory map was freed successfully, False otherwise.
        """
        if mem_map_name not in self.allocated_mem_maps:
            logger.error('Cannot find shared memory in list of allocations: %s', mem_map_name)
            return False
        mem_map = self.allocated_mem_maps[mem_map_name]
        success = self.file_accessor.delete_mem_map(mem_map_name, mem_map)
        del self.allocated_mem_maps[mem_map_name]
        if not success:
            logger.error('Cannot delete shared memory: %s', mem_map_name)
            return False
        return True
