# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from . import rpcexception


class RetryContext:
    """Check https://docs.microsoft.com/en-us/azure/azure-functions/
       functions-bindings-error-pages?tabs=python#retry-policies-preview"""

    def __init__(self,
                 retry_count: int,
                 max_retry_count: int,
                 rpc_exception: rpcexception.RpcException) -> None:
        self.__retry_count = retry_count
        self.__max_retry_count = max_retry_count
        self.__rpc_exception = rpc_exception

    @property
    def retry_count(self) -> int:
        """Gets the current retry count from retry-context"""
        return self.__retry_count

    @property
    def max_retry_count(self) -> int:
        """Gets the max retry count from retry-context"""
        return self.__max_retry_count

    @property
    def exception(self) -> rpcexception.RpcException:
        return self.__rpc_exception
