# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from . import TraceContext
from . import RetryContext


class Context:

    def __init__(self,
                 func_name: str,
                 func_dir: str,
                 invocation_id: str,
                 trace_context: TraceContext,
                 retry_context: RetryContext) -> None:
        self.__func_name = func_name
        self.__func_dir = func_dir
        self.__invocation_id = invocation_id
        self.__trace_context = trace_context
        self.__retry_context = retry_context

    @property
    def invocation_id(self) -> str:
        return self.__invocation_id

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
