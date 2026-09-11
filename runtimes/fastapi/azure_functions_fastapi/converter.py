# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI to Azure Functions Converter
Converts FastAPI route metadata to Azure Functions function metadata
"""
import typing
import uuid
from typing import Dict, List

from .indexer import FastAPIFunctionMetadata


class AzureFunctionInfo(typing.NamedTuple):
    """Azure Function metadata compatible with Python worker"""
    name: str
    function_id: str
    directory: str
    script_file: str
    entry_point: str
    bindings: List[Dict]
    is_async: bool
    route_path: str
    http_methods: List[str]
    route_handler: typing.Callable


class FastAPIConverter:
    """Converts FastAPI routes to Azure Functions metadata"""
    
    def __init__(self):
        self.functions: Dict[str, AzureFunctionInfo] = {}
    
    def convert_to_azure_functions(
        self, 
        fastapi_functions: List[FastAPIFunctionMetadata]
    ) -> List[AzureFunctionInfo]:
        """
        Convert FastAPI function metadata to Azure Functions metadata
        
        Each FastAPI route becomes an HTTP-triggered Azure Function
        """
        azure_functions = []
        
        for fastapi_func in fastapi_functions:
            # Create HTTP trigger binding
            http_trigger = {
                "name": "req",
                "type": "httpTrigger",
                "direction": "in",
                "authLevel": "anonymous",
                "methods": [m.lower() for m in fastapi_func.http_methods],
                "route": fastapi_func.route_path.lstrip('/')
            }
            
            # Create HTTP output binding
            http_output = {
                "name": "$return",
                "type": "http",
                "direction": "out"
            }
            
            # Create Azure Function info
            azure_func = AzureFunctionInfo(
                name=fastapi_func.name,
                function_id=fastapi_func.function_id,
                directory=fastapi_func.directory,
                script_file=fastapi_func.function_script_file,
                entry_point=fastapi_func.name,
                bindings=[http_trigger, http_output],
                is_async=fastapi_func.is_async,
                route_path=fastapi_func.route_path,
                http_methods=fastapi_func.http_methods,
                route_handler=fastapi_func.route_handler
            )
            
            azure_functions.append(azure_func)
            self.functions[azure_func.function_id] = azure_func
        
        return azure_functions
    
    def get_function(self, function_id: str) -> typing.Optional[AzureFunctionInfo]:
        """Get function info by ID"""
        return self.functions.get(function_id)
