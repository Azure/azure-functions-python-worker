# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Runtime - Extends the runtime base package

This runtime implementation provides native FastAPI support for Azure Functions.
It auto-registers with the runtime base when imported.
"""
from runtimes.base import RuntimeBase
from .handle_event import (
    worker_init_request,
    functions_metadata_request,
    function_environment_reload_request,
    invocation_request,
    function_load_request
)
from .version import VERSION


class Runtime(RuntimeBase):
    """
    FastAPI Runtime implementation.
    
    This class auto-registers with RuntimeTrackerMeta when defined,
    allowing the proxy worker to discover it dynamically.
    """
    runtime_name = "fastapi"
    
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
