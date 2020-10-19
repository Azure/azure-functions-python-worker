# -*- coding: utf-8 -*-

import os
import sys
import mmap
import time
import struct
import hashlib
import urllib.parse
from .memorymappedfile_constants import MemoryMappedFileConstants as consts

"""
TODO
Clean up this class and use logger instead of prints
"""
class FileAccessor:
    @staticmethod
    def _open_mmap_file_linux(map_name):
        """Get the file descriptor of an existing memory map.
        """
        escaped_map_name = urllib.parse.quote_plus(map_name)
        for mmap_temp_dir in consts.TEMP_DIRS:
            filename = "%s/%s/%s" % (mmap_temp_dir, consts.TEMP_DIR_SUFFIX, escaped_map_name)
            try:
                file = open(filename, "r+b")
                return file
            except FileNotFoundError:
                pass
        raise FileNotFoundError("File for '%s' does not exist" % (map_name))

    @staticmethod
    def open_mmap(map_name, map_size, access=mmap.ACCESS_READ):
        """Open an existing memory map.
        """
        try:
            if os.name == "posix":
                file = FileAccessor._open_mmap_file_linux(map_name)
                mmap_ret = mmap.mmap(file.fileno(), map_size, access=access)
            else:
                mmap_ret = mmap.mmap(-1, map_size, map_name, access=access)
            mmap_ret.seek(0)
            return mmap_ret
        except ValueError:
            # mmap length is greater than file size
            #print("Cannot open memory map '%s': %s" % (map_name, value_error))
            return None
        except FileNotFoundError:
            # TODO Log Error
            return None

    @staticmethod
    def _create_mmap_dir_linux():
        """Create a directory to create memory maps.
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
                print.error("Cannot create dir '%s': %s" % (dirname, str(ex)))

    @staticmethod
    def _create_mmap_file_linux(map_name, map_size):
        """Get the file descriptor for a new memory map.
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
            FileAccessor._create_mmap_dir_linux()
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

    @staticmethod
    def create_mmap(map_name, map_size):
        """Create a new memory map.
        """
        if os.name == 'posix':
            file = FileAccessor._create_mmap_file_linux(map_name, map_size)
            mem_map = mmap.mmap(file, map_size, mmap.MAP_SHARED, mmap.PROT_WRITE)
        else:
            # Windows creates it when trying to open it
            mem_map = FileAccessor.open_mmap(map_name, map_size, mmap.ACCESS_WRITE)
        # Verify that the file is actually created and not existing before
        mem_map.seek(0)
        byte_read = mem_map.read(1)
        if byte_read != b'\x00':
            raise Exception("Memory map '%s' already exists" % (map_name))
        mem_map.seek(0)
        return mem_map

    @staticmethod
    def delete_mmap(map_name, mmap):
        """Delete a memory map.
        """
        if os.name == 'posix':
            try:
                file = FileAccessor._open_mmap_file_linux(map_name)
                os.remove(file.name)
            except FileNotFoundError:
                pass # Nothing to do if the file is not there anyway
        mmap.close()