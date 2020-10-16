# -*- coding: utf-8 -*-

# TODO use protobuf to define these constants between C# and Python
class MemoryMappedFileConstants:
    # Directories in Linux where the memory maps can be found
    TEMP_DIRS = ["/dev/shm", "/tmp"]
    # Suffix for the temp directories containing memory maps
    TEMP_DIR_SUFFIX = "AzureFunctions"

    # The length of the MD5 at the beginning of the content shared memory
    REQUESTS_MD5_MARK_LENGTH = 16
    # The MD5 that marks that we can read
    REQUESTS_MD5_MARK_RESET = b'\x00' * REQUESTS_MD5_MARK_LENGTH

    # The length of a long which is the length of the header in the content mmap
    CONTENT_LENGTH_NUM_BYTES = 8
    # The length of control flag
    CONTROL_FLAG_NUM_BYTES = 1
    # The length of the header: control flag + content length
    CONTENT_HEADER_TOTAL_BYTES = CONTROL_FLAG_NUM_BYTES + CONTENT_LENGTH_NUM_BYTES