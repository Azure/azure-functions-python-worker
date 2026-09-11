# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Wrapper utilities for FastAPI runtime"""
import functools
from typing import Type, Union


def attach_message_to_exception(expt_type: Union[Type[Exception], tuple], 
                                message: str, 
                                debug_logs: str = ""):
    """
    Decorator to attach additional context to exceptions
    
    Args:
        expt_type: Exception type or tuple of exception types to catch
        message: Message to append to the exception
        debug_logs: Additional debug information
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except expt_type as e:
                # Append additional context to the exception message
                enhanced_message = f"{str(e)}\n{message}"
                if debug_logs:
                    enhanced_message += f"\n{debug_logs}"
                
                # Re-raise with enhanced message
                raise type(e)(enhanced_message) from e
        
        return wrapper
    return decorator
