# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Indexer - Discovers FastAPI routes and converts them to Azure Functions metadata
"""
import importlib
import inspect
import os.path
import pathlib
import sys
import typing
from typing import Dict, List, Optional

import fastapi.routing as fastapi_routing
from fastapi import FastAPI
from fastapi.routing import APIRoute

from .utils.constants import PYTHON_SCRIPT_FILE_NAME_DEFAULT


def _iter_effective_routes(routes):
    route_iterator = getattr(
        fastapi_routing, "_iter_routes_with_context", None)
    if route_iterator is None:
        for route in routes:
            yield route, None
        return

    yield from route_iterator(routes)


class FastAPIFunctionMetadata(typing.NamedTuple):
    """Metadata for a function generated from a FastAPI route"""
    name: str
    function_id: str
    route_path: str
    http_methods: List[str]
    function_script_file: str
    directory: str
    route_handler: typing.Callable
    is_async: bool


class FastAPIIndexer:
    """Indexes a FastAPI application and generates function metadata"""
    
    def __init__(
        self,
        fastapi_app: FastAPI,
        function_script_file: str = PYTHON_SCRIPT_FILE_NAME_DEFAULT,
    ):
        self.app = fastapi_app
        self.function_script_file = function_script_file
        self.functions: List[FastAPIFunctionMetadata] = []
    
    def index_routes(self) -> List[FastAPIFunctionMetadata]:
        """
        Scan all routes in the FastAPI app and create function metadata
        for each route that will be converted to an Azure Function
        """
        functions = []
        
        for route, route_context in _iter_effective_routes(self.app.routes):
            if isinstance(route, APIRoute):
                # Generate a unique function name from the route
                function_name = self._generate_function_name(route)
                
                # Get HTTP methods for this route
                http_methods = list(route.methods)
                route_path = (
                    route_context.path if route_context else route.path)
                route_handler = (
                    route_context.endpoint if route_context else route.endpoint)
                
                # Create metadata for this route
                metadata = FastAPIFunctionMetadata(
                    name=function_name,
                    function_id=function_name,  # Using name as ID for now
                    route_path=route_path,
                    http_methods=http_methods,
                    function_script_file=self.function_script_file,
                    directory=os.getcwd(),
                    route_handler=route_handler,
                    is_async=inspect.iscoroutinefunction(route_handler)
                )
                
                functions.append(metadata)
        
        self.functions = functions
        return functions
    
    def _generate_function_name(self, route: APIRoute) -> str:
        """
        Get the function name from the route's endpoint function.
        
        Uses the actual function name defined by the developer, e.g.:
        @app.get("/users/{id}")
        async def get_user_by_id(id: int):  # <- Uses "get_user_by_id"
        """
        # Use the actual function name from the endpoint
        if route.endpoint and hasattr(route.endpoint, '__name__'):
            return route.endpoint.__name__
        
        # Fallback: generate from path if endpoint name not available
        path = route.path.strip('/')
        path = path.replace('/', '_').replace('{', '').replace('}', '')
        path = path.replace('-', '_')
        
        method = list(route.methods)[0].lower() if route.methods else 'http'
        
        if path:
            return f"{method}_{path}"
        else:
            return f"{method}_root"


def index_fastapi_app(function_path: str) -> List[FastAPIFunctionMetadata]:
    """
    Index a FastAPI application from the given module path
    
    Args:
        function_path: Path to the Python module containing the FastAPI app
        
    Returns:
        List of FastAPIFunctionMetadata for each route in the app
    """
    module_name = pathlib.Path(function_path).stem
    imported_module = importlib.import_module(module_name)
    
    # Find the FastAPI app instance
    app: Optional[FastAPI] = None
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
        raise ValueError(
            f"Could not find FastAPI app instance in {function_path}. "
            "Please ensure you have created a FastAPI() instance."
        )
    
    # Index all routes
    indexer = FastAPIIndexer(
        app, function_script_file=pathlib.Path(function_path).name)
    return indexer.index_routes()
