# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import traceback


def extend_exception_message(exc: Exception, msg: str) -> Exception:
    # Reconstruct exception message
    # From: ImportModule: no module name
    # To: ImportModule: no module name. msg
    old_tb = exc.__traceback__
    old_msg = getattr(exc, 'msg', None) or str(exc) or ''
    new_msg = (old_msg.rstrip('.') + '. ' + msg).rstrip()
    new_excpt = type(exc)(new_msg).with_traceback(old_tb)
    return new_excpt


def marshall_exception_trace(exc: Exception) -> str:
    try:
        # Use traceback.format_exception to capture the full exception chain
        # This includes __cause__ and __context__ chained exceptions
        full_traceback = traceback.format_exception(type(exc), exc, exc.__traceback__)

        # If it's a ModuleNotFoundError, we might want to clean up the traceback
        if isinstance(exc, ModuleNotFoundError):
            # For consistency with the original logic, we'll still filter
            # but we need to work with the formatted strings
            filtered_lines = []
            for line in full_traceback:
                if '<frozen importlib._bootstrap>' not in line and \
                   '<frozen importlib._bootstrap_external>' not in line:
                    filtered_lines.append(line)
            if filtered_lines:
                return ''.join(filtered_lines)

        return ''.join(full_traceback)
    except Exception as sub_exc:
        return (f'Could not extract traceback. '
                f'Sub-exception: {type(sub_exc).__name__}: {str(sub_exc)}')


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


def serialize_exception_as_str(exc: Exception):
    try:
        message = str(type(exc).__name__) + ": " + str(exc)
    except Exception:
        message = ('Unhandled exception in function. '
                   'Could not serialize original exception message.')

    try:
        stack_trace = marshall_exception_trace(exc)
    except Exception:
        stack_trace = ''

    return "Message: " + message + " | " + "Stack Trace: " + stack_trace
