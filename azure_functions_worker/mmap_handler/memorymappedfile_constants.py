# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


class MemoryMappedFileConstants:
    # Directories in Unix where the memory maps can be found
    UNIX_TEMP_DIRS = ["/dev/shm"]

    # Suffix for the temp directories containing memory maps in Unix
    UNIX_TEMP_DIR_SUFFIX = "AzureFunctions"

    # The length of a bool which is the length of the part of the header flag specifying if the
    # memory map is already created and used.
    # This is to distinguish between new memory maps and ones that were previously created and may
    # be in use already.
    DIRTY_BIT_FLAG_NUM_BYTES = 1

    # The length of a long which is the length of the part of the header specifying content length
    # in the memory map.
    CONTENT_LENGTH_NUM_BYTES = 8

    # The total length of the header
    CONTENT_HEADER_TOTAL_BYTES = DIRTY_BIT_FLAG_NUM_BYTES + CONTENT_LENGTH_NUM_BYTES

    # A flag to indicate that the memory map has been created, may be in use and is not new.
    DIRTY_BIT_SET = b'\x01'

    # Zero byte.
    # E.g. Used to compare the first byte of a newly created memory map against this; if it is a
    # non-zero byte then the memory map was already created.
    ZERO_BYTE = b'\x00'
