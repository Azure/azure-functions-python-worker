# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from .file_accessor_unix import FileAccessorUnix
from .file_accessor_windows import FileAccessorWindows


class FileAccessorFactory:
    """
    For creating the platform-appropriate instance of FileAccessor to perform
    memory map related operations.
    """
    @staticmethod
    def create_file_accessor():
        if os.name == 'nt':
            return FileAccessorWindows()
        return FileAccessorUnix()
