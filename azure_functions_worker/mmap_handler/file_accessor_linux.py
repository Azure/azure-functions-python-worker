# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import mmap
import urllib.parse
from typing import Optional
from .memorymappedfile_constants import MemoryMappedFileConstants as consts
from .file_accessor import FileAccessor


class FileAccessorLinux(FileAccessor):
    """
    For accessing memory maps.
    This implements the FileAccessor interface for Linux.
    """
    def open_mem_map(self, map_name: str, map_size: int , access: int) -> Optional[mmap.mmap]:
        try:
            fd = self._open_mem_map_file(map_name)
            mem_map = mmap.mmap(fd.fileno(), map_size, access=access)
            mem_map.seek(0)
            return mem_map
        except Exception as e:
            # TODO Log Error
            print(e)
            return None

    def create_mem_map(self, map_name: str, map_size: int) -> Optional[mmap.mmap]:
        fd = self._create_mem_map_file(map_name, map_size)
        mem_map = mmap.mmap(fd, map_size, mmap.MAP_SHARED, mmap.PROT_WRITE)
        if not self._verify_new_map_created(map_name, mem_map):
            raise Exception("Memory map '%s' already exists" % (map_name))
        return mem_map

    def delete_mem_map(self, map_name: str, mem_map: mmap.mmap) -> bool:
        try:
            fd = self._open_mem_map_file(map_name)
            os.remove(fd.name)
        except FileNotFoundError:
            # TODO log debug
            return False
        mem_map.close()
        return True

    def _open_mem_map_file(self, map_name: str):
        """
        Get the file descriptor of an existing memory map.
        """
        escaped_map_name = urllib.parse.quote_plus(map_name)
        for mmap_temp_dir in consts.TEMP_DIRS:
            filename = "%s/%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX, escaped_map_name)
            try:
                fd = open(filename, "r+b")
                return fd
            except FileNotFoundError:
                # TODO log debug
                pass
        raise FileNotFoundError("File for '%s' does not exist" % (map_name))

    def _create_mem_map_dir(self):
        """
        Create a directory to create memory maps.
        """
        for mmap_temp_dir in consts.TEMP_DIRS:
            dirname = "%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX)
            if os.path.isdir(dirname):
                # One of the directories already exists, no need
                return
            try:
                os.makedirs(dirname)
                return
            except Exception as ex:
                print("Cannot create dir '%s': %s" % (dirname, str(ex)))

    def _create_mem_map_file(self, map_name: str, map_size: int):
        """
        Get the file descriptor for a new memory map.
        """
        escaped_map_name = urllib.parse.quote_plus(map_name)
        dir_exists = False
        for mmap_temp_dir in consts.TEMP_DIRS:
            # Check if the file already exists
            filename = "%s/%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX, escaped_map_name)
            if os.path.exists(filename):
                raise Exception("File '%s' for memory map '%s' already exists" %
                                (filename, map_name))
            # Check if the parent directory exists
            dir_name = "%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX)
            if os.path.isdir(dir_name):
                dir_exists = True
        # Check if any of the parent directories exists
        if not dir_exists:
            self._create_mem_map_dir()
        # Create the file
        for mmap_temp_dir in consts.TEMP_DIRS:
            filename = "%s/%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX, escaped_map_name)
            try:
                fd = os.open(filename, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
                # Write 0s to allocate
                bytes_written = os.write(fd, b'\x00' * map_size)
                if bytes_written != map_size:
                    print("Cannot write 0s into new memory map file '%s': %d != %d" %
                        (filename, bytes_written, map_size))
                return fd
            except Exception as ex:
                print("Cannot create memory map file '%s': %s" % (filename, ex))
        raise Exception("Cannot create memory map file for '%s'" % (map_name))