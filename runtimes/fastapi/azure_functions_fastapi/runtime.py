# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Runtime - Extends the runtime base package

This runtime implementation provides native FastAPI support for Azure Functions.
It auto-registers with the runtime base when imported.
"""
import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from azurefunctions.extensions.base import RuntimeBase
from .handle_event import (
    worker_init_request,
    functions_metadata_request,
    function_environment_reload_request,
    invocation_request,
    function_load_request
)
from .utils.executor import invocation_id_cv as _invocation_id_cv
from .version import VERSION as _VERSION


class Runtime(RuntimeBase):
    """
    FastAPI Runtime implementation.
    
    This class auto-registers with RuntimeTrackerMeta when defined,
    allowing the proxy worker to discover it dynamically.
    
    The FastAPI runtime is async-only and does not use thread pools.
    """
    runtime_name = "fastapi"
    
    @property
    def VERSION(self) -> str:
        """Get the runtime version string."""
        return _VERSION
    
    async def worker_init_request(self, request):
        return await worker_init_request(request)
    
    async def functions_metadata_request(self, request):
        return await functions_metadata_request(request)
    
    async def function_load_request(self, request):
        return await function_load_request(request)
    
    async def invocation_request(self, request):
        return await invocation_request(request)
    
    async def function_environment_reload_request(self, request):
        return await function_environment_reload_request(request)
    
    def start_threadpool_executor(self) -> None:
        """
        No-op for FastAPI runtime (async-only).
        
        The FastAPI runtime doesn't use a threadpool executor since all
        operations are async.
        """
        pass
    
    def stop_threadpool_executor(self) -> None:
        """
        No-op for FastAPI runtime (async-only).
        
        The FastAPI runtime doesn't use a threadpool executor since all
        operations are async.
        """
        pass
    
    def get_threadpool_executor(self) -> Optional[ThreadPoolExecutor]:
        """
        Return None for FastAPI runtime (async-only).
        
        The FastAPI runtime doesn't use a threadpool executor since all
        operations are async.
        
        Returns:
            None
        """
        return None
    
    @property
    def invocation_id_cv(self) -> contextvars.ContextVar:
        """
        Get the invocation ID context variable.
        
        Returns:
            ContextVar for tracking invocation IDs
        """
        return _invocation_id_cv


# Export for backward compatibility
__all__ = (
    'Runtime',
    'worker_init_request',
    'functions_metadata_request',
    'function_environment_reload_request',
    'invocation_request',
    'function_load_request',
    'VERSION'
)
