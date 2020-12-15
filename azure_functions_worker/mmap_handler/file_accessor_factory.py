# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from .file_accessor_linux import FileAccessorLinux
from .file_accessor_windows import FileAccessorWindows


class FileAccessorFactory:
    @staticmethod
    def create_file_accessor():
        if os.name == 'posix':
            return FileAccessorLinux()
        else:
            return FileAccessorWindows()