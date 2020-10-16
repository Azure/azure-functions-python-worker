# -*- coding: utf-8 -*-

import enum


class MemoryMappedFileControlFlags(enum.Enum):
    """Flag to indicate state of memory mapped file.
    Note: Must be kept in sync with the DotNet runtime version of this:
    TODO path to MemStore constants
    """
    UNKNOWN = 0
    READY_TO_READ = 1
    READY_TO_DISPOSE = 2
    WRITE_IN_PROGRESS = 3
    PENDING_READ = 4


class MemoryMappedFileControlFlagsUtils:
    @staticmethod
    def is_available(control_flag):
        if control_flag == MemoryMappedFileControlFlags.UNKNOWN.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.WRITE_IN_PROGRESS.value:
            return True
        elif control_flag == MemoryMappedFileControlFlags.READY_TO_READ.value:
            return True
        elif control_flag == MemoryMappedFileControlFlags.READY_TO_DISPOSE.value:
            return True
        else:
            raise Exception("Unknown control flag: '%s'" % (control_flag))

    @staticmethod
    def is_readable(control_flag):
        if control_flag == MemoryMappedFileControlFlags.UNKNOWN.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.WRITE_IN_PROGRESS.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.READY_TO_READ.value:
            return True
        elif control_flag == MemoryMappedFileControlFlags.READY_TO_DISPOSE.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.PENDING_READ.value:
            return False
        else:
            raise Exception("Unknown control flag: '%s'" % (control_flag))

    @staticmethod
    def is_disposable(control_flag):
        if control_flag == MemoryMappedFileControlFlags.UNKNOWN.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.WRITE_IN_PROGRESS.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.READY_TO_READ.value:
            return False
        elif control_flag == MemoryMappedFileControlFlags.READY_TO_DISPOSE.value:
            return True
        elif control_flag == MemoryMappedFileControlFlags.PENDING_READ.value:
            return False
        else:
            raise Exception("Unknown control flag: '%s'" % (control_flag))
