# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Runtime for Azure Functions

Imports the Runtime class which auto-registers with the base package.
"""
from .runtime import Runtime
from .handle_event import (
    worker_init_request,
    functions_metadata_request,
    function_environment_reload_request,
    invocation_request,
    function_load_request
)
from .version import VERSION

__all__ = (
    'Runtime',
    'worker_init_request',
    'functions_metadata_request',
    'function_environment_reload_request',
    'invocation_request',
    'function_load_request',
    'VERSION'
)
