# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Runtime Event Handler
Main entry point for handling Azure Functions worker events for FastAPI apps
"""
import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, MutableMapping, Optional

from fastapi import FastAPI

from .converter import AzureFunctionInfo, FastAPIConverter
from .handler import execute_fastapi_route
from .loader import load_function_metadata
from .utils.tracing import serialize_exception
from .utils.helpers import get_worker_metadata
from .logging import logger
from .version import VERSION


# Module-level state
_converter: Optional[FastAPIConverter] = None
_fastapi_app: Optional[FastAPI] = None
_metadata_result: Optional[List] = None
_function_path: Optional[str] = None
protos = None


async def worker_init_request(request):
    """
    Handle WorkerInitRequest - Initialize the FastAPI runtime
    
    This is called when the worker starts up
    """
    logger.info(f"FastAPI Runtime: received WorkerInitRequest, Version {VERSION}")
    
    global protos
    init_request = request.request.worker_init_request
    host_capabilities = init_request.capabilities
    protos = request.properties.get("protos")
    
    # Declare capabilities
    capabilities = {
        "RawHttpBodyBytes": "true",
        "TypedDataCollection": "true",
        "RpcHttpBodyOnly": "true",
        "WorkerStatus": "true",
        "RpcHttpTriggerMetadataRemoved": "true",
    }
    
    # Index in init by default. Fail if an exception occurs.
    try:
        script_file_name = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
        function_app_directory = init_request.function_app_directory
        function_path = os.path.join(function_app_directory, script_file_name)
        
        # Index the FastAPI app
        global _fastapi_app, _converter, _metadata_result
        _fastapi_app, _metadata_result, _converter = load_function_metadata(
            function_path, function_app_directory, protos)
    except Exception as ex:
        logger.error(f"Failed to index FastAPI app during init: {ex}", exc_info=True)
        return protos.WorkerInitResponse(
            capabilities=capabilities,
            worker_metadata=get_worker_metadata(protos),
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(
                    ex, protos))
        )
    
    logger.info("Successfully completed WorkerInitRequest")
    return protos.WorkerInitResponse(
        capabilities=capabilities,
        worker_metadata=get_worker_metadata(protos),
        result=protos.StatusResult(status=protos.StatusResult.Success)
    )

async def functions_metadata_request(request):
    """
    Handle FunctionMetadataRequest - Return metadata for all discovered FastAPI routes
    
    This tells the host about all the functions (routes) available in the FastAPI app
    """
    script_file_name = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
    function_app_directory = os.getcwd()
    function_path = os.path.join(function_app_directory, script_file_name)
    
    global _fastapi_app, _converter, _metadata_result
    
    # If we haven't indexed yet, do it now
    if not _metadata_result:
        function_path = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
        await load_function_metadata(function_path)
    
    if not _metadata_result:
        logger.error("No FastAPI functions were discovered")
        return protos.FunctionMetadataResponse(
            use_default_metadata_indexing=False,
            function_metadata_results=[],
            result=protos.StatusResult(
                status=protos.StatusResult.Failure)
        )
    
    return protos.FunctionMetadataResponse(
        use_default_metadata_indexing=False,
        function_metadata_results=_metadata_result,
        result=protos.StatusResult(
            status=protos.StatusResult.Success))


async def function_load_request(request):
    """
    Handle FunctionLoadRequest - Load a specific function
    
    For FastAPI, functions are already "loaded" during indexing, so this is mostly a no-op
    """
    logger.info("FastAPI Runtime: received FunctionLoadRequest")
    
    func_request = request.request.function_load_request
    function_id = func_request.function_id
    
    # Verify the function exists
    if _converter:
        func_info = _converter.get_function(function_id)
        if func_info:
            logger.info(f"Function {function_id} loaded: {func_info.route_path}")
            return protos.FunctionLoadResponse(
                function_id=function_id,
                result=protos.StatusResult(status=protos.StatusResult.Success)
            )
    
    logger.error(f"Function {function_id} not found")
    return protos.FunctionLoadResponse(
        function_id=function_id,
        result=protos.StatusResult(
            status=protos.StatusResult.Failure)
    )


async def invocation_request(request):
    """
    Handle InvocationRequest - Execute a FastAPI route
    
    This is called when a function is invoked (e.g., HTTP request comes in)
    """
    logger.info("FastAPI Runtime: received InvocationRequest")
    
    invoc_request = request.request.invocation_request
    function_id = invoc_request.function_id
    invocation_id = invoc_request.invocation_id
    
    try:
        # Get the function info
        if not _converter:
            raise RuntimeError("FastAPI converter not initialized")
        
        func_info = _converter.get_function(function_id)
        if not func_info:
            raise RuntimeError(f"Function {function_id} not found")
        
        # Extract HTTP request from input data
        azure_request = None
        for input_data in invoc_request.input_data:
            if input_data.data.http:
                azure_request = input_data.data.http
                break
        
        if not azure_request:
            raise RuntimeError("No HTTP request data found")
        
        # Execute the FastAPI route
        response = await execute_fastapi_route(
            app=_fastapi_app,
            azure_request=azure_request,
            route_handler=func_info.route_handler,
            route_path=func_info.route_path,
            is_async=func_info.is_async
        )
        
        # Build response
        http_response = protos.RpcHttp(
            status_code=str(response.get('status_code', 200)),
            headers=response.get('headers', {}),
            body=protos.TypedData(string=response.get('body', ''))
        )
        
        return protos.InvocationResponse(
            invocation_id=invocation_id,
            return_value=protos.TypedData(http=http_response),
            result=protos.StatusResult(status=protos.StatusResult.Success)
        )
        
    except Exception as e:
        logger.error(f"Error executing function {function_id}: {e}", exc_info=True)
        return protos.InvocationResponse(
            invocation_id=invocation_id,
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(e, protos)
            )
        )


async def function_environment_reload_request(request):
    """
    Handle FunctionEnvironmentReloadRequest - Reload the environment
    
    This might be called when the function app needs to reload (e.g., code changes)
    """
    logger.info("FastAPI Runtime: received FunctionEnvironmentReloadRequest")
    
    # Re-index the FastAPI app
    try:
        script_file_name = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
        function_app_directory = os.getcwd()
        function_path = os.path.join(function_app_directory, script_file_name)
        
        global _fastapi_app, _converter, _metadata_result
        _fastapi_app, _metadata_result, _converter = load_function_metadata(
            function_path, function_app_directory, protos)
        
        return protos.FunctionEnvironmentReloadResponse(
            capabilities={},
            worker_metadata=get_worker_metadata(protos),
            result=protos.StatusResult(
                status=protos.StatusResult.Success))
    except Exception as e:
        logger.error(f"Error reloading environment: {e}", exc_info=True)
        return protos.FunctionEnvironmentReloadResponse(
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(e, protos)
            )
        )
