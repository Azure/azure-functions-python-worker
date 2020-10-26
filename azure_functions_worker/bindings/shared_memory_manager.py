# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import uuid
from ..logging import logger
from ..mmap_handler.file_writer import FileWriter
from ..mmap_handler.file_reader import FileReader
from ..mmap_handler.file_accessor import FileAccessor


class SharedMemoryManager:
    """
    Performs all operations related to reading/writing data from/to Shared
    Memory.
    """
    def __init__(self):
        self.allocated_mmaps = {} # type dict[map_name, mmap]

    def is_enabled(self) -> bool:
        """
        Whether supported types should be transferred between Functions host
        and the worker using shared memory.
        """
        return True

    def is_supported(self, datum) -> bool:
        """
        Whether the given Datum object can be transferred to the Functions host
        using shared memory.
        """
        if datum.type == 'bytes':
            # TODO gochaudh: Check for min size config
            # Is there a common place to put configs shared b/w host and worker?
            return True
        elif datum.type == 'string':
            return True
        else:
            return False

    def get_bytes(self, map_name: str, offset: int, count: int) -> bytes:
        """
        Reads data from the given Memory Mapped File with the provided name,
        starting at the provided offset and reading a total of count bytes.
        Returns a tuple containing the binary data read from shared memory
        if successful, None otherwise.
        """
        logger.info('Reading bytes from shared memory: %s', map_name)
        data = FileReader.read_content_as_bytes(map_name, offset)
        return data

    def get_string(self, map_name: str, offset: int, count: int) -> str:
        logger.info('Reading string from shared memory: %s', map_name)
        data = FileReader.read_content_as_string(map_name, offset)
        return data

    def put_bytes(self, data: bytes) -> str:
        """
        Writes the given bytes into shared memory.
        Returns the name of the Memory Mapped File into which the data was
        written if succesful, None otherwise.
        """
        map_name = str(uuid.uuid4())
        logger.info('Writing bytes to shared memory: %s', map_name)
        mmap = FileWriter.create_with_content_bytes(map_name, data)

        # Hold a reference to the mmap to prevent it from closing before the
        # host has read it.
        self.allocated_mmaps[map_name] = mmap

        return map_name

    def put_string(self, data: str) -> str:
        """
        Writes the given string into shared memory.
        Returns the name of the Memory Mapped File into which the data was
        written if succesful, None otherwise.
        """
        map_name = str(uuid.uuid4())
        logger.info('Writing string to shared memory: %s', map_name)
        mmap = FileWriter.create_with_content_string(map_name, data)

        # Hold a reference to the mmap to prevent it from closing before the
        # host has read it.
        self.allocated_mmaps[map_name] = mmap

        return map_name

    def free_map(self, map_name: str):
        """
        """
        if map_name in self.allocated_mmaps:
            mmap = self.allocated_mmaps[map_name]
            FileAccessor.delete_mmap(map_name, mmap)
            del self.allocated_mmaps[map_name]

