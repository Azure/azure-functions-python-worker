# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


class SharedMemoryConstants:
    # Directories in Unix where the memory maps can be found
    UNIX_TEMP_DIRS = ["/dev/shm"]

    # Suffix for the temp directories containing memory maps in Unix
    UNIX_TEMP_DIR_SUFFIX = "AzureFunctions"

    # The length of a bool which is the length of the part of the header flag
    # specifying if the memory map is already created and used.
    # This is to distinguish between new memory maps and ones that were
    # previously created and may be in use already.
    MEM_MAP_INITIALIZED_FLAG_NUM_BYTES = 1

    # The length of a long which is the length of the part of the header
    # specifying content length in the memory map.
    CONTENT_LENGTH_NUM_BYTES = 8

    # The total length of the header
    CONTENT_HEADER_TOTAL_BYTES = MEM_MAP_INITIALIZED_FLAG_NUM_BYTES + \
        CONTENT_LENGTH_NUM_BYTES

    # A flag to indicate that the memory map has been initialized, may be in use
    # and is not new.
    # This represents a boolean value of True.
    MEM_MAP_INITIALIZED_FLAG = b'\x01'

    # A flag to indicate that the memory map has not yet been initialized.
    # This represents a boolean value of False.
    MEM_MAP_UNINITIALIZED_FLAG = b'\x00'

    # Minimum size (in number of bytes) an object must be in order for it to be
    # transferred over shared memory.
    # If the object is smaller than this, gRPC is used.
    # Note: This needs to be consistent among the host and workers.
    #       e.g. in the host, it is defined in SharedMemoryConstants.cs
    MIN_BYTES_FOR_SHARED_MEM_TRANSFER = 1024 * 1024  # 1 MB

    # Maximum size (in number of bytes) an object must be in order for it to be
    # transferred over shared memory.
    # This limit is imposed because initializing objects like greater than 2GB
    # is not allowed in DotNet.
    # Ref: https://stackoverflow.com/a/3944336/3132415
    # Note: This needs to be consistent among the host and workers.
    #       e.g. in the host, it is defined in SharedMemoryConstants.cs
    MAX_BYTES_FOR_SHARED_MEM_TRANSFER = 2 * 1024 * 1024 * 1024  # 2 GB

    # This is what the size of a character is in DotNet. Can be verified by
    # doing "sizeof(char)".
    # To keep the limits consistent, when determining if a string can be
    # transferred over shared memory, we multiply the number of characters
    # by this constant.
    # Corresponding logic in the host can be found in SharedMemoryManager.cs
    SIZE_OF_CHAR_BYTES = 2
