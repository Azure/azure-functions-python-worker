# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import functools
from typing import Callable, Any

from .common import is_envvar_true, is_envvar_false
from .tracing import extend_exception_message
from ..logging import logger


# def handle_invocation_before_and_after(f):
#     @functools.wraps(f)
#     async def wrapper(self, request):
#         # Pre-processing code here
#         print("Pre-processing before the main function call.")
#         invocation_id = request.invocation_request.invocation_id
#         function_id = request.invocation_request.function_id
#         fi: functions.FunctionInfo = self._functions.get_function(
#             function_id)
#         is_http_trigger_func = await self.is_http_trigger_func(fi)
#         if not is_http_trigger_func:
#             return await f(self, request)
#
#         http_request = await http_coordinator.wait_and_get_http_invoc_request(
#             invocation_id)
#         args["req"] = http_request
#
#         try:
#             # Call the async function
#             result = await f(self, request)
#             # Post-processing code here
#             print("Post-processing after the main function call.")
#             return result
#         except Exception as e:
#             # You can add exception handling if needed
#             print("An error occurred: ", e)
#             raise  # Re-raise the exception
#
#     return wrapper

def enable_feature_by(flag: str,
                      default: Any = None,
                      flag_default: bool = False) -> Callable:
    def decorate(func):
        def call(*args, **kwargs):
            if is_envvar_true(flag):
                return func(*args, **kwargs)
            if flag_default and not is_envvar_false(flag):
                return func(*args, **kwargs)
            return default

        return call

    return decorate


def disable_feature_by(flag: str,
                       default: Any = None,
                       flag_default: bool = False) -> Callable:
    def decorate(func):
        def call(*args, **kwargs):
            if is_envvar_true(flag):
                return default
            if flag_default and not is_envvar_false(flag):
                return default
            return func(*args, **kwargs)

        return call

    return decorate


def attach_message_to_exception(expt_type: Exception, message: str,
                                debug_logs=None) -> Callable:
    def decorate(func):
        def call(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except expt_type as e:
                if debug_logs is not None:
                    logger.error(debug_logs)
                raise extend_exception_message(e, message)

        return call

    return decorate
