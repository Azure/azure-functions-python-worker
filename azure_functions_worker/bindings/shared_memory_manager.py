# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import uuid
from ..logging import logger


class SharedMemoryManager:
    """
    Performs all operations related to reading/writing data from/to Shared
    Memory.
    """
    def __init__(self):
        pass

    @staticmethod
    def is_enabled():
        """
        Whether supported types should be transferred between Functions host
        and the worker using Shared Memory.
        """
        return True

    def get(self, mmap_name: str, offset: int, count: int) -> (bytes):
        """
        Reads data from the given Memory Mapped File with the provided name,
        starting at the provided offset and reading a total of count bytes.
        Returns a tuple containing the binary data read from Shared Memory
        if successful, None otherwise.
        """
        logger.info('Reading from Shared Memory: %s', mmap_name)
        return 'foo'.encode('utf-8')

    def put(self, data: bytes) -> (str):
        """
        Writes the given data into Shared Memory.
        Returns the name of the Memory Mapped File into which the data was
        written if succesful, None otherwise.
        """
        mmap_name = str(uuid.uuid4())
        return mmap_name
