# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from dataclasses import dataclass

from . import rpcexception


@dataclass
class RetryContext:
    """Gets the current retry count from retry-context"""
    retry_count: int

    """Gets the max retry count from retry-context"""
    max_retry_count: int

    rpc_exception: rpcexception.RpcException
