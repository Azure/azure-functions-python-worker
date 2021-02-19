# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

class SharedMemoryMetadata:
    """
    Information about a shared memory region.
    """
    def __init__(self, mem_map_name, count):
        # Name of the memory map
        self.mem_map_name = mem_map_name
        # Number of bytes of content in the memory map
        self.count = count