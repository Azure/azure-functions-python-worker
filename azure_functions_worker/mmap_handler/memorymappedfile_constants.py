# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# TODO use protobuf to define these constants between C# and Python?
class MemoryMappedFileConstants:
    # Directories in Linux where the memory maps can be found
    TEMP_DIRS = ["/dev/shm"]
    # Suffix for the temp directories containing memory maps
    TEMP_DIR_SUFFIX = "AzureFunctions"

    # The length of a long which is the length of the header in the content memory map
    CONTENT_LENGTH_NUM_BYTES = 8
    # The length of the header: content length
    CONTENT_HEADER_TOTAL_BYTES = CONTENT_LENGTH_NUM_BYTES

    # Zero byte.
    # E.g. Used to compare the first byte of a newly created memory map against this; if it is a
    # non-zero byte then the memory map was already created.
    ZERO_BYTE = b'\x00'
