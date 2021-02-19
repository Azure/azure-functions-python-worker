# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import mmap
from typing import Optional
from io import BufferedRandom
from .shared_memory_constants import SharedMemoryConstants as consts
from .file_accessor import FileAccessor
from ..logging import logger


class FileAccessorUnix(FileAccessor):
    """
    For accessing memory maps.
    This implements the FileAccessor interface for Unix platforms.
    """
    def open_mem_map(
            self,
            mem_map_name: str,
            mem_map_size: int,
            access: int = mmap.ACCESS_READ) -> Optional[mmap.mmap]:
        fd = self._open_mem_map_file(mem_map_name)
        if fd is None:
            return None
        mem_map = mmap.mmap(fd.fileno(), mem_map_size, access=access)
        return mem_map

    def create_mem_map(self, mem_map_name: str, mem_map_size: int) \
            -> Optional[mmap.mmap]:
        fd = self._create_mem_map_file(mem_map_name, mem_map_size)
        if fd is None:
            return None
        mem_map = mmap.mmap(fd, mem_map_size, mmap.MAP_SHARED, mmap.PROT_WRITE)
        if self._is_mem_map_initialized(mem_map):
            raise Exception(f'Memory map {mem_map_name} already exists')
        self._set_mem_map_initialized(mem_map)
        return mem_map

    def delete_mem_map(self, mem_map_name: str, mem_map: mmap.mmap) -> bool:
        try:
            fd = self._open_mem_map_file(mem_map_name)
            os.remove(fd.name)
        except Exception as e:
            # In this case, we don't want to fail right away but log that
            # deletion was unsuccessful.
            # These logs can help identify if we may be leaking memory and not
            # cleaning up the created memory maps.
            logger.error(f'Cannot delete memory map {mem_map_name} - {e}',
                         exc_info=True)
            return False
        mem_map.close()
        return True

    def _open_mem_map_file(self, mem_map_name: str) -> Optional[BufferedRandom]:
        """
        Get the file descriptor of an existing memory map.
        Returns the BufferedRandom stream to the file.
        """
        # Iterate over all the possible directories where the memory map could
        # be present and try to open it.
        for mem_map_temp_dir in consts.UNIX_TEMP_DIRS:
            file_path = os.path.join(mem_map_temp_dir,
                                     consts.UNIX_TEMP_DIR_SUFFIX, mem_map_name)
            try:
                fd = open(file_path, 'r+b')
                return fd
            except FileNotFoundError:
                pass
        # The memory map was not found in any of the known directories
        logger.error(f'Cannot open memory map {mem_map_name}')
        return None

    def _create_mem_map_dir(self) -> bool:
        """
        Create a directory to create memory maps.
        Returns True if either a valid directory already exists or one was
        created successfully, False otherwise.
        """
        # Iterate over all the possible directories where the memory map could
        # be created and try to create in one of them.
        for mem_map_temp_dir in consts.UNIX_TEMP_DIRS:
            dir_path = os.path.join(mem_map_temp_dir,
                                    consts.UNIX_TEMP_DIR_SUFFIX)
            if os.path.isdir(dir_path):
                # One of the directories already exists, no need
                return True
            try:
                os.makedirs(dir_path)
                return True
            except Exception:
                # We try to create a directory in each of the applicable
                # directory paths until we successfully create one or one that
                # already exists is found.
                # Even if this fails, we keep trying others.
                pass
        # Could not create a directory in any of the applicable directory paths.
        # We will not be able to create any memory maps so we fail.
        logger.error(f'Cannot create directory for memory maps')
        return False

    def _create_mem_map_file(self, mem_map_name: str, mem_mem_map_size: int) \
            -> Optional[int]:
        """
        Get the file descriptor for a new memory map.
        Returns the file descriptor.
        """
        dir_exists = False
        for mem_map_temp_dir in consts.UNIX_TEMP_DIRS:
            # Check if the file already exists
            file_path = os.path.join(mem_map_temp_dir,
                                     consts.UNIX_TEMP_DIR_SUFFIX, mem_map_name)
            if os.path.exists(file_path):
                raise Exception(
                    f'File {file_path} for memory map {mem_map_name} '
                    f'already exists')
            # Check if the parent directory exists
            dir_path = os.path.join(mem_map_temp_dir,
                                    consts.UNIX_TEMP_DIR_SUFFIX)
            if os.path.isdir(dir_path):
                dir_exists = True
        # Check if any of the parent directories exists
        if not dir_exists:
            if not self._create_mem_map_dir():
                return None
        # Create the file
        for mem_map_temp_dir in consts.UNIX_TEMP_DIRS:
            file_path = os.path.join(mem_map_temp_dir,
                                     consts.UNIX_TEMP_DIR_SUFFIX, mem_map_name)
            try:
                fd = os.open(file_path, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
                # Write 0s to allocate
                # TODO use truncate here instead of zeroeing out the memory
                bytes_written = os.write(fd, b'\x00' * mem_mem_map_size)
                if bytes_written != mem_mem_map_size:
                    raise Exception(
                        f'Cannot write 0s into new memory map {file_path} '
                        f'({bytes_written} != {mem_mem_map_size})')
                return fd
            except Exception:
                # If the memory map could not be created in this directory, we
                # keep trying in other applicable directories.
                pass
        # Could not create the memory map in any of the applicable directory
        # paths so we fail.
        logger.error(
            f'Cannot create memory map {mem_map_name} with size '
            f'{mem_mem_map_size}')
        return None
