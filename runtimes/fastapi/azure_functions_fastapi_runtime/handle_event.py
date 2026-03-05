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
from .indexer import index_fastapi_app
from .version import VERSION


# Module-level state
_converter: Optional[FastAPIConverter] = None
_fastapi_app: Optional[FastAPI] = None
_metadata_result: Optional[List] = None
_function_path: Optional[str] = None
protos = None

logger = logging.getLogger('azure_functions_fastapi_runtime')


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
    
    # Try to index the FastAPI app during init
    try:
        function_path = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
        await load_function_metadata(function_path)
    except Exception as e:
        logger.warning(f"Could not index FastAPI app during init: {e}")
    
    return protos.StreamingMessage(
        request_id=request.request.request_id,
        worker_init_response=protos.WorkerInitResponse(
            capabilities=capabilities,
            result=protos.StatusResult(status=protos.StatusResult.Success)
        )
    )


async def functions_metadata_request(request):
    """
    Handle FunctionMetadataRequest - Return metadata for all discovered FastAPI routes
    
    This tells the host about all the functions (routes) available in the FastAPI app
    """
    logger.info("FastAPI Runtime: received FunctionMetadataRequest")
    
    global _metadata_result
    
    # If we haven't indexed yet, do it now
    if not _metadata_result:
        function_path = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
        await load_function_metadata(function_path)
    
    if not _metadata_result:
        logger.error("No FastAPI functions were discovered")
        return protos.StreamingMessage(
            request_id=request.request.request_id,
            function_metadata_response=protos.FunctionMetadataResponse(
                function_metadata_results=[],
                result=protos.StatusResult(
                    status=protos.StatusResult.Failure,
                    result="No FastAPI functions discovered"
                )
            )
        )
    
    return protos.StreamingMessage(
        request_id=request.request.request_id,
        function_metadata_response=protos.FunctionMetadataResponse(
            function_metadata_results=_metadata_result,
            result=protos.StatusResult(status=protos.StatusResult.Success)
        )
    )


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
            return protos.StreamingMessage(
                request_id=request.request.request_id,
                function_load_response=protos.FunctionLoadResponse(
                    function_id=function_id,
                    result=protos.StatusResult(status=protos.StatusResult.Success)
                )
            )
    
    logger.error(f"Function {function_id} not found")
    return protos.StreamingMessage(
        request_id=request.request.request_id,
        function_load_response=protos.FunctionLoadResponse(
            function_id=function_id,
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                result=f"Function {function_id} not found"
            )
        )
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
        
        return protos.StreamingMessage(
            request_id=request.request.request_id,
            invocation_response=protos.InvocationResponse(
                invocation_id=invocation_id,
                return_value=protos.TypedData(http=http_response),
                result=protos.StatusResult(status=protos.StatusResult.Success)
            )
        )
        
    except Exception as e:
        logger.error(f"Error executing function {function_id}: {e}", exc_info=True)
        return protos.StreamingMessage(
            request_id=request.request.request_id,
            invocation_response=protos.InvocationResponse(
                invocation_id=invocation_id,
                result=protos.StatusResult(
                    status=protos.StatusResult.Failure,
                    result=str(e)
                )
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
        function_path = os.environ.get("PYTHON_SCRIPT_FILE_NAME", "function_app.py")
        await load_function_metadata(function_path)
        
        return protos.StreamingMessage(
            request_id=request.request.request_id,
            function_environment_reload_response=protos.FunctionEnvironmentReloadResponse(
                result=protos.StatusResult(status=protos.StatusResult.Success)
            )
        )
    except Exception as e:
        logger.error(f"Error reloading environment: {e}", exc_info=True)
        return protos.StreamingMessage(
            request_id=request.request.request_id,
            function_environment_reload_response=protos.FunctionEnvironmentReloadResponse(
                result=protos.StatusResult(
                    status=protos.StatusResult.Failure,
                    result=str(e)
                )
            )
        )


async def load_function_metadata(function_path: str):
    """
    Index the FastAPI app and generate function metadata
    
    This discovers all routes in the FastAPI app and converts them to Azure Functions
    """
    global _converter, _fastapi_app, _metadata_result, _function_path
    
    logger.info(f"Indexing FastAPI app from {function_path}")
    
    # Add current directory to Python path
    current_dir = os.getcwd()
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    # Index the FastAPI app
    fastapi_functions = index_fastapi_app(function_path)
    logger.info(f"Discovered {len(fastapi_functions)} FastAPI routes")
    
    # Get the FastAPI app instance for later use
    import importlib
    import pathlib
    module_name = pathlib.Path(function_path).stem
    imported_module = importlib.import_module(module_name)
    
    for attr_name in dir(imported_module):
        attr = getattr(imported_module, attr_name, None)
        if isinstance(attr, FastAPI):
            _fastapi_app = attr
            break
    
    # Convert to Azure Functions metadata
    _converter = FastAPIConverter()
    azure_functions = _converter.convert_to_azure_functions(fastapi_functions)
    
    # Build protobuf metadata
    _metadata_result = []
    for func in azure_functions:
        # Build bindings proto
        bindings_proto = {}
        for binding in func.bindings:
            direction_map = {
                'in': protos.BindingInfo.Direction.in_,
                'out': protos.BindingInfo.Direction.out,
                'inout': protos.BindingInfo.Direction.inout
            }
            
            bindings_proto[binding['name']] = protos.BindingInfo(
                type=binding['type'],
                direction=direction_map.get(binding['direction'], protos.BindingInfo.Direction.in_)
            )
        
        # Create function metadata
        metadata = protos.RpcFunctionMetadata(
            name=func.name,
            function_id=func.function_id,
            directory=func.directory,
            script_file=func.script_file,
            entry_point=func.entry_point,
            language="python",
            bindings=bindings_proto,
            properties={"WorkerIndexed": "True", "FastAPIRoute": func.route_path}
        )
        
        _metadata_result.append(metadata)
    
    _function_path = function_path
    logger.info(f"Successfully indexed {len(_metadata_result)} functions")
