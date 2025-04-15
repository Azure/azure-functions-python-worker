# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import threading
from typing import Type

from .retrycontext import RetryContext
from .tracecontext import TraceContext


class Context:
    def __init__(self,
                 func_name: str,
                 func_dir: str,
                 invocation_id: str,
                 thread_local_storage: Type[threading.local],
                 trace_context: TraceContext,
                 retry_context: RetryContext) -> None:
        self.__func_name = func_name
        self.__func_dir = func_dir
        self.__invocation_id = invocation_id
        self.__thread_local_storage = thread_local_storage
        self.__trace_context = trace_context
        self.__retry_context = retry_context

    @property
    def invocation_id(self) -> str:
        return self.__invocation_id

    @property
    def thread_local_storage(self) -> Type[threading.local]:
        return self.__thread_local_storage

    @property
    def function_name(self) -> str:
        return self.__func_name

    @property
    def function_directory(self) -> str:
        return self.__func_dir

    @property
    def trace_context(self) -> TraceContext:
        return self.__trace_context

    @property
    def retry_context(self) -> RetryContext:
        return self.__retry_context


def get_context(invoc_request, name: str,
                directory: str) -> Context:
    """ For more information refer:
    https://aka.ms/azfunc-invocation-context
    """
    trace_context = TraceContext(
        invoc_request.trace_context.trace_parent,
        invoc_request.trace_context.trace_state,
        invoc_request.trace_context.attributes)

    retry_context = RetryContext(
        invoc_request.retry_context.retry_count,
        invoc_request.retry_context.max_retry_count,
        invoc_request.retry_context.exception)

    return Context(
        name, directory, invoc_request.invocation_id,
        threading.local(), trace_context, retry_context)
