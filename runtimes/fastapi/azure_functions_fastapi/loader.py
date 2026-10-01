# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Loader - Indexes FastAPI applications and generates Azure Functions metadata
"""
import importlib
import os.path
import pathlib
import sys
from typing import Dict, List, Tuple

from fastapi import FastAPI

from .converter import FastAPIConverter
from .indexer import index_fastapi_app
from .logging import logger
from .utils.constants import (
    METADATA_PROPERTIES_WORKER_INDEXED,
    PYTHON_LANGUAGE_RUNTIME,
    PYTHON_SCRIPT_FILE_NAME,
    PYTHON_SCRIPT_FILE_NAME_DEFAULT,
)
from .utils.app_setting_manager import get_app_setting
from .utils.wrappers import attach_message_to_exception


def build_binding_protos(protos, func_info) -> Dict:
    """
    Build protobuf binding metadata for a FastAPI route
    
    For FastAPI, all functions are HTTP triggered, so we create:
    - An HTTP trigger binding (input)
    - An HTTP output binding (output)
    """
    binding_protos = {}
    
    for binding in func_info.bindings:
        # Map string direction to protobuf enum value
        if binding['direction'] == 'in':
            direction = 0  # BindingInfo.Direction.in
        elif binding['direction'] == 'out':
            direction = 1  # BindingInfo.Direction.out
        elif binding['direction'] == 'inout':
            direction = 2  # BindingInfo.Direction.inout
        else:
            direction = 0  # Default to 'in'
        
        binding_protos[binding['name']] = protos.BindingInfo(
            type=binding['type'],
            direction=direction
        )
    
    return binding_protos


def build_raw_bindings(func_info) -> List[str]:
    """
    Build raw bindings as a list of JSON strings for FastAPI function
    
    Each binding becomes a separate JSON string in the list, matching
    the format expected by the Azure Functions host.
    
    Returns:
        List of JSON strings, one per binding
    """
    import json
    
    raw_bindings = []
    for binding in func_info.bindings:
        raw_binding = {
            "name": binding['name'],
            "type": binding['type'],
            "direction": binding['direction'].upper()  # Direction must be uppercase: IN, OUT, INOUT
        }
        
        # Add HTTP-specific properties for trigger
        if binding['type'] == 'httpTrigger':
            raw_binding["authLevel"] = "ANONYMOUS"  # Uppercase to match v2 runtime
            raw_binding["methods"] = [m.lower() for m in func_info.http_methods]
            # For Azure Functions, omit 'route' key entirely for root path
            # Setting route to empty string doesn't work - the host won't match it
            route = func_info.route_path.lstrip('/')
            if route:  # Only set route if it's not empty (not root path)
                raw_binding["route"] = route
        
        # Each binding becomes a separate JSON string
        raw_bindings.append(json.dumps(raw_binding))
    
    return raw_bindings


def process_indexed_function(protos, fastapi_app: FastAPI, 
                            azure_functions, function_dir: str) -> Tuple[List, Dict]:
    """
    Process indexed FastAPI functions and generate RpcFunctionMetadata
    
    This converts FastAPI routes into Azure Functions metadata that matches
    the structure expected by the host.
    
    Args:
        protos: Protobuf definitions module
        fastapi_app: The FastAPI application instance
        azure_functions: List of AzureFunctionInfo from converter
        function_dir: The function app directory path
        
    Returns:
        Tuple of (metadata_results, bindings_logs)
        - metadata_results: List of RpcFunctionMetadata protobuf objects
        - bindings_logs: Dict mapping functions to their binding logs
    """
    fx_metadata_results = []
    fx_bindings_logs = {}
    
    for func_info in azure_functions:
        # Build binding protobuf metadata
        binding_protos = build_binding_protos(protos, func_info)
        
        # Build raw bindings JSON
        raw_bindings = build_raw_bindings(func_info)
        
        # Create RpcFunctionMetadata matching v2 runtime structure
        function_metadata = protos.RpcFunctionMetadata(
            name=func_info.name,
            function_id=func_info.function_id,
            managed_dependency_enabled=False,  # Not applicable for FastAPI
            directory=function_dir,
            script_file=func_info.script_file,
            entry_point=func_info.entry_point,
            is_proxy=False,  # Not supported in V4
            language=PYTHON_LANGUAGE_RUNTIME,
            bindings=binding_protos,
            raw_bindings=raw_bindings,
            retry_options=None,  # FastAPI doesn't use retry policies at function level
            properties={
                METADATA_PROPERTIES_WORKER_INDEXED: "True",
                "FastAPIRoute": func_info.route_path,
                "HttpMethods": ",".join(func_info.http_methods)
            }
        )
        
        fx_metadata_results.append(function_metadata)
        
        # Create binding logs for debugging
        bindings_log = {}
        for binding in func_info.bindings:
            bindings_log[binding['name']] = {
                "type": binding['type'],
                "direction": binding['direction']
            }
        fx_bindings_logs[func_info.name] = bindings_log
    
    return fx_metadata_results, fx_bindings_logs


@attach_message_to_exception(
    expt_type=(ImportError, ModuleNotFoundError),
    message="Cannot find module. Please check the requirements.txt file for the "
            "missing module. Current sys.path: " + " ".join(sys.path),
    debug_logs="Error when indexing FastAPI app. Sys Path:" + " ".join(sys.path))
def index_function_app_fastapi(function_path: str) -> Tuple[FastAPI, List]:
    """
    Index a FastAPI application and return the app instance and discovered routes
    
    Args:
        function_path: Path to the Python module containing the FastAPI app
        
    Returns:
        Tuple of (fastapi_app, fastapi_functions)
        - fastapi_app: The FastAPI application instance
        - fastapi_functions: List of FastAPIFunctionMetadata for each route
        
    Raises:
        ValueError: If no FastAPI app is found or multiple apps are defined
        ImportError/ModuleNotFoundError: If the module cannot be imported
    """
    module_name = pathlib.Path(function_path).stem
    imported_module = importlib.import_module(module_name)
    
    # Find the FastAPI app instance
    app: FastAPI = None
    for attr_name in dir(imported_module):
        attr = getattr(imported_module, attr_name, None)
        if isinstance(attr, FastAPI):
            if not app:
                app = attr
            else:
                raise ValueError(
                    "More than one FastAPI app instance found. "
                    "Please ensure only one FastAPI() instance is defined at the module level."
                )
    
    if not app:
        script_file_name = get_app_setting(
            setting=PYTHON_SCRIPT_FILE_NAME,
            default_value=PYTHON_SCRIPT_FILE_NAME_DEFAULT)
        raise ValueError(
            f"Could not find FastAPI app instance in {script_file_name}. "
            "Please ensure you have created a FastAPI() instance."
        )
    
    # Index all routes in the FastAPI app
    fastapi_functions = index_fastapi_app(function_path)
    
    logger.info(f"Successfully indexed FastAPI app with {len(fastapi_functions)} routes")
    
    return app, fastapi_functions


def load_function_metadata(function_path: str, function_dir: str, protos) -> Tuple[FastAPI, List]:
    """
    Load and index a FastAPI application, converting routes to Azure Functions metadata
    
    This is the main entry point for indexing a FastAPI app. It:
    1. Discovers the FastAPI app instance
    2. Indexes all routes
    3. Converts routes to Azure Functions
    4. Generates RpcFunctionMetadata for the host
    
    Args:
        function_path: Path to the Python module containing the FastAPI app
        function_dir: Directory containing the function app
        protos: Protobuf definitions module
        
    Returns:
        Tuple of (fastapi_app, metadata_results)
        - fastapi_app: The FastAPI application instance
        - metadata_results: List of RpcFunctionMetadata protobuf objects
    """
    function_app_directory = os.path.dirname(os.path.abspath(function_path))
    if function_app_directory not in sys.path:
        sys.path.insert(0, function_app_directory)
    
    logger.info(f"Indexing FastAPI app from {function_path}")
    
    # Index the FastAPI app and get the app instance
    fastapi_app, fastapi_functions = index_function_app_fastapi(function_path)
    
    logger.info(f"Discovered {len(fastapi_functions)} FastAPI routes")
    
    # Convert FastAPI routes to Azure Functions
    converter = FastAPIConverter()
    azure_functions = converter.convert_to_azure_functions(fastapi_functions)
    
    # Generate RpcFunctionMetadata for each function
    metadata_results, bindings_logs = process_indexed_function(
        protos, fastapi_app, azure_functions, function_dir)
    
    # Log function details
    indexed_function_logs: List[str] = []
    for func_info in azure_functions:
        bindings_info = ", ".join([
            f"{b['name']}({b['type']})" for b in func_info.bindings
        ])
        function_log = (
            f"Function Name: {func_info.name}, "
            f"Route: {func_info.route_path}, "
            f"Methods: {func_info.http_methods}, "
            f"Bindings: [{bindings_info}]"
        )
        indexed_function_logs.append(function_log)
    
    logger.info(
        f"Successfully indexed FastAPI app: "
        f"function_count={len(metadata_results)}, "
        f"functions={'; '.join(indexed_function_logs)}"
    )
    
    return fastapi_app, metadata_results, converter
