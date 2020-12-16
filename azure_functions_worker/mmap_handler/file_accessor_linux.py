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
    def open_mmap(self, map_name: str, map_size: int , access: int) -> Optional[mmap.mmap]:
        try:
            file = self._open_mmap_file(map_name, access)
            mem_map = mmap.mmap(file.fileno(), map_size, access=access)
            mem_map.seek(0)
            return mem_map
        except Exception as e:
            # TODO Log Error
            print(e)
            return None

    def create_mmap(self, map_name: str, map_size: int) -> Optional[mmap.mmap]:
        file = self._create_mmap_file(map_name, map_size)
        mem_map = mmap.mmap(file, map_size, mmap.MAP_SHARED, mmap.PROT_WRITE)
        if not self._verify_new_map_created(map_name, mem_map):
            raise Exception("Memory map '%s' already exists" % (map_name))
        return mem_map

    def delete_mmap(self, map_name: str, mem_map: mmap.mmap) -> Optional[mmap.mmap]:
        try:
            file = self._open_mmap_file(map_name)
            os.remove(file.name)
        except FileNotFoundError:
            # TODO log debug
            pass # Nothing to do if the file is not there anyway
        mem_map.close()

    def _open_mmap_file(self, map_name: str):
        """
        Get the file descriptor of an existing memory map.
        """
        escaped_map_name = urllib.parse.quote_plus(map_name)
        for mmap_temp_dir in consts.TEMP_DIRS:
            filename = "%s/%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX, escaped_map_name)
            try:
                file = open(filename, "r+b")
                return file
            except FileNotFoundError:
                # TODO log debug
                pass
        raise FileNotFoundError("File for '%s' does not exist" % (map_name))

    def _create_mmap_dir(self):
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

    def _create_mmap_file(self, map_name: str, map_size: int):
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
            self._create_mmap_dir()
        # Create the file
        for mmap_temp_dir in consts.TEMP_DIRS:
            filename = "%s/%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX, escaped_map_name)
            try:
                file = os.open(filename, os.O_CREAT | os.O_TRUNC | os.O_RDWR)
                # Write 0s to allocate
                bytes_written = os.write(file, b'\x00' * map_size)
                if bytes_written != map_size:
                    print("Cannot write 0s into new memory map file '%s': %d != %d" %
                        (filename, bytes_written, map_size))
                return file
            except Exception as ex:
                print("Cannot create memory map file '%s': %s" % (filename, ex))
        raise Exception("Cannot create memory map file for '%s'" % (map_name))