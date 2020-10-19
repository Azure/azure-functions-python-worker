# -*- coding: utf-8 -*-

# TODO use protobuf to define these constants between C# and Python
class MemoryMappedFileConstants:
    # Directories in Linux where the memory maps can be found
    TEMP_DIRS = ["/dev/shm"]
    # Suffix for the temp directories containing memory maps
    TEMP_DIR_SUFFIX = "AzureFunctions"

    # The length of a long which is the length of the header in the content mmap
    CONTENT_LENGTH_NUM_BYTES = 8
    # The length of the header: content length
    CONTENT_HEADER_TOTAL_BYTES = CONTENT_LENGTH_NUM_BYTES