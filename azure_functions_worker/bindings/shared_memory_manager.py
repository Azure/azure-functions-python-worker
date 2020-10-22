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
        self.allocated_mmaps = {} # type dict[string, [(mmap_name, mmap)]

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
        else:
            return False

    def get_bytes(self, mmap_name: str, offset: int, count: int) -> bytes:
        """
        Reads data from the given Memory Mapped File with the provided name,
        starting at the provided offset and reading a total of count bytes.
        Returns a tuple containing the binary data read from shared memory
        if successful, None otherwise.
        """
        logger.info('Reading from shared memory: %s', mmap_name)
        data = FileReader.read_content_as_bytes(mmap_name, offset)
        return data

    def put_bytes(self, data: bytes, invocation_id: str) -> str:
        """
        Writes the given data into shared memory.
        Returns the name of the Memory Mapped File into which the data was
        written if succesful, None otherwise.
        """
        mmap_name = str(uuid.uuid4())
        logger.info('Writing to shared memory: %s', mmap_name)
        mmap = FileWriter.create_with_content_bytes(mmap_name, data)

        if invocation_id not in self.allocated_mmaps:
            self.allocated_mmaps[invocation_id] = []
        self.allocated_mmaps[invocation_id].append((mmap_name, mmap))

        return mmap_name

    def free(self, invocation_id: str):
        """
        Free up the resources allocated for the given invocation_id.
        This includes closing and deleting mmaps that were produced as outputs
        during the given invocation_id.
        """
        if invocation_id in self.allocated_mmaps:
            for mmap_name, mmap in self.allocated_mmaps[invocation_id]:
                FileAccessor.delete_mmap(mmap_name, mmap)
            del self.allocated_mmaps[invocation_id]
