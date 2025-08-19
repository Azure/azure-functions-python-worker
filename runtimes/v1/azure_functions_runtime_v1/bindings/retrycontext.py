# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from dataclasses import dataclass


class RpcException:
    def __init__(self,
                 source: str,
                 stack_trace: str,
                 message: str) -> None:
        self.__source = source
        self.__stack_trace = stack_trace
        self.__message = message

    @property
    def source(self) -> str:
        return self.__source

    @property
    def stack_trace(self) -> str:
        return self.__stack_trace

    @property
    def message(self) -> str:
        return self.__message


@dataclass
class RetryContext:
    """Gets the current retry count from retry-context"""
    retry_count: int
    """Gets the max retry count from retry-context"""
    max_retry_count: int
    rpc_exception: RpcException
