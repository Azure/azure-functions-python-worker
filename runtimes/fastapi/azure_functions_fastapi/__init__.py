# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Runtime for Azure Functions

Imports the Runtime class which auto-registers with the base package.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .runtime import Runtime
from .handle_event import (
    worker_init_request,
    functions_metadata_request,
    function_environment_reload_request,
    invocation_request,
    function_load_request
)
from .utils.executor import invocation_id_cv
from .version import VERSION


# Threadpool executor stubs - FastAPI runtime is async-only
def start_threadpool_executor() -> None:
    """
    No-op for FastAPI runtime (async-only).
    
    The FastAPI runtime doesn't use a threadpool executor since all
    operations are async. This function is provided for API compatibility
    with the proxy worker.
    """
    pass


def stop_threadpool_executor() -> None:
    """
    No-op for FastAPI runtime (async-only).
    
    This function is provided for API compatibility with the proxy worker.
    """
    pass


def get_threadpool_executor() -> Optional[ThreadPoolExecutor]:
    """
    Return None for FastAPI runtime (async-only).
    
    The FastAPI runtime doesn't use a threadpool executor since all
    operations are async.
    
    Returns:
        None
    """
    return None


# Version namespace for _library_worker.version.VERSION access pattern
class version:
    """Version namespace to support _library_worker.version.VERSION access."""
    VERSION = VERSION


__all__ = (
    'Runtime',
    'worker_init_request',
    'functions_metadata_request',
    'function_environment_reload_request',
    'invocation_request',
    'function_load_request',
    'start_threadpool_executor',
    'stop_threadpool_executor',
    'get_threadpool_executor',
    'invocation_id_cv',
    'VERSION',
    'version'
)
