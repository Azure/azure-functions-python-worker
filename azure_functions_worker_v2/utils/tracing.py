# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import traceback
from traceback import StackSummary, extract_tb
from typing import List


def extend_exception_message(exc: Exception, msg: str) -> Exception:
    # Reconstruct exception message
    # From: ImportModule: no module name
    #   To: ImportModule: no module name. msg
    old_tb = exc.__traceback__
    old_msg = getattr(exc, 'msg', None) or str(exc) or ''
    new_msg = (old_msg.rstrip('.') + '. ' + msg).rstrip()
    new_excpt = type(exc)(new_msg).with_traceback(old_tb)
    return new_excpt


def marshall_exception_trace(exc: Exception) -> str:
    stack_summary: StackSummary = extract_tb(exc.__traceback__)
    if isinstance(exc, ModuleNotFoundError):
        stack_summary = _marshall_module_not_found_error(stack_summary)
    return ''.join(stack_summary.format())


def _marshall_module_not_found_error(tbss: StackSummary) -> StackSummary:
    tbss = _remove_frame_from_stack(tbss, '<frozen importlib._bootstrap>')
    tbss = _remove_frame_from_stack(
        tbss, '<frozen importlib._bootstrap_external>')
    return tbss


def _remove_frame_from_stack(tbss: StackSummary,
                             framename: str) -> StackSummary:
    filtered_stack_list: List[traceback.FrameSummary] = \
        list(filter(lambda frame: getattr(frame,
                                          'filename') != framename, tbss))
    filtered_stack: StackSummary = StackSummary.from_list(filtered_stack_list)
    return filtered_stack


def serialize_exception(exc: Exception, protos):
    try:
        message = str(type(exc).__name__) + ": " + str(exc)
    except Exception:
        message = ('Unhandled exception in function. '
                   'Could not serialize original exception message.')

    try:
        stack_trace = marshall_exception_trace(exc)
    except Exception:
        stack_trace = ''

    return protos.RpcException(message=message, stack_trace=stack_trace)
