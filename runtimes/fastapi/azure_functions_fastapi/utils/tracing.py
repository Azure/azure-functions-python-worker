# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Tracing utilities for FastAPI runtime"""
import traceback


def serialize_exception(exc: Exception, protos):
    """
    Serialize an exception to protobuf format
    
    Args:
        exc: The exception to serialize
        protos: The protobuf module
        
    Returns:
        RpcException protobuf object
    """
    tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    
    return protos.RpcException(
        message=str(exc),
        stack_trace=tb
    )
