# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under
from dataclasses import dataclass
from enum import Enum


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


class RetryPolicy(Enum):
    """Retry policy for the function invocation"""

    MAX_RETRY_COUNT = "max_retry_count"
    STRATEGY = "strategy"
    DELAY_INTERVAL = "delay_interval"
    MINIMUM_INTERVAL = "minimum_interval"
    MAXIMUM_INTERVAL = "maximum_interval"


@dataclass
class RetryContext:
    """Gets the current retry count from retry-context"""
    retry_count: int

    """Gets the max retry count from retry-context"""
    max_retry_count: int

    rpc_exception: RpcException
