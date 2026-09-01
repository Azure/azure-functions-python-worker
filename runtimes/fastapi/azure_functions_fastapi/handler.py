# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Request/Response Handler
Handles execution of FastAPI routes and conversion between Azure Functions and ASGI
"""
import asyncio
import json
import re
import typing
from typing import Any, Dict, List, Optional
from io import BytesIO
from urllib.parse import urlsplit

from fastapi import FastAPI
from starlette.requests import Request
from starlette.datastructures import Headers, QueryParams


class ASGIRequest:
    """ASGI-compatible request object built from Azure Functions HTTP request"""
    
    def __init__(self, azure_request):
        self.azure_request = azure_request
        self.method = azure_request.method
        self.url = azure_request.url
        self.headers = dict(azure_request.headers) if azure_request.headers else {}
        self.query_params = dict(azure_request.params) if azure_request.params else {}
        self.body = azure_request.get_body() if hasattr(azure_request, 'get_body') else b''
        self.route_params = azure_request.route_params if hasattr(azure_request, 'route_params') else {}


class FastAPIHandler:
    """Handles execution of FastAPI routes in Azure Functions context"""
    
    def __init__(self, app: FastAPI):
        self.app = app
    
    async def handle_request(
        self,
        azure_request,
        route_handler: typing.Callable,
        route_path: str,
        is_async: bool
    ) -> Dict[str, Any]:
        """
        Execute a FastAPI route handler and return Azure Functions-compatible response
        
        Args:
            azure_request: Azure Functions HTTP request
            route_handler: The FastAPI route handler function
            route_path: The route path pattern (e.g., "/items/{item_id}")
            is_async: Whether the handler is async
            
        Returns:
            Dict with status_code, headers, and body for Azure Functions response
        """
        try:
            # Get the request URL path (convert to string if it's a URL object)
            request_url = str(azure_request.url) if hasattr(azure_request.url, '__str__') else azure_request.url
            
            # Extract path parameters by matching the route pattern
            path_params = self._extract_path_params(route_path, request_url)
            
            # Build ASGI scope for the request
            scope = self._build_scope(azure_request, route_path, path_params)
            
            # Create a Starlette Request object that FastAPI can work with
            starlette_request = self._create_starlette_request(azure_request, scope, path_params)
            
            # Build the arguments to pass to the route handler
            # This includes path params, query params, and the Request object if needed
            kwargs = await self._build_handler_kwargs(
                route_handler, 
                starlette_request, 
                path_params
            )
            
            # Execute the handler
            if is_async:
                result = await route_handler(**kwargs)
            else:
                result = route_handler(**kwargs)
            
            # Convert result to Azure Functions response format
            return self._format_response(result)
            
        except Exception as e:
            # Return error response
            return {
                'status_code': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': str(e)})
            }
    
    def _extract_path_params(self, route_path: str, request_url: str) -> Dict[str, str]:
        """
        Extract path parameters from the request URL by matching against the route pattern.
        
        For example:
            route_path = "/items/{item_id}"
            request_url = "http://localhost:7071/api/items/123"
            returns: {"item_id": "123"}
        """
        # Remove /api prefix if present in the request URL
        url_path = request_url.split('?')[0]  # Remove query string
        if '://' in url_path:
            # Extract just the path from full URL
            url_path = '/' + url_path.split('/', 3)[-1] if url_path.count('/') >= 3 else '/'
        
        # Remove /api prefix if it exists
        if url_path.startswith('/api/'):
            url_path = url_path[4:]  # Remove '/api'
        elif url_path.startswith('/api'):
            url_path = url_path[4:]  # Remove '/api'
        
        # If path is empty after stripping prefix, it represents root path
        if not url_path:
            url_path = '/'
        
        # Debug logging
        from .logging import logger
        logger.info(f"[FastAPI Handler] Request URL: {request_url}")
        logger.info(f"[FastAPI Handler] Extracted path: {url_path}")
        logger.info(f"[FastAPI Handler] Route pattern: {route_path}")
        
        # Ensure route_path has leading slash
        if not route_path.startswith('/'):
            route_path = '/' + route_path
        
        # Convert FastAPI route pattern to regex
        # Replace {param} with named capture groups
        pattern = re.sub(r'\{([^}]+)\}', r'(?P<\1>[^/]+)', route_path)
        pattern = '^' + pattern + '$'
        
        logger.info(f"[FastAPI Handler] Regex pattern: {pattern}")
        
        # Match the URL path against the pattern
        match = re.match(pattern, url_path)
        if match:
            logger.info(f"[FastAPI Handler] Path matched! Params: {match.groupdict()}")
            return match.groupdict()
        
        logger.warning(f"[FastAPI Handler] No match! url_path='{url_path}' pattern='{pattern}'")
        return {}
    
    def _build_scope(self, azure_request, route_path: str, path_params: Dict[str, str]) -> Dict[str, Any]:
        """Build ASGI scope from Azure Functions request"""
        # Get the URL path (convert to string if it's a URL object)
        url_str = str(azure_request.url) if hasattr(azure_request.url, '__str__') else azure_request.url
        url_path = urlsplit(url_str).path

        root_path = ''
        if route_path == '/' and url_path.endswith('/'):
            root_path = url_path[:-1].rstrip('/')
        elif url_path.endswith(route_path):
            root_path = url_path[:-len(route_path)].rstrip('/')
        
        # Build query string from params
        query_string = b''
        if hasattr(azure_request, 'params') and azure_request.params:
            query_parts = [f"{k}={v}" for k, v in azure_request.params.items()]
            query_string = '&'.join(query_parts).encode('utf-8')
        
        return {
            'type': 'http',
            'method': azure_request.method.upper(),
            'path': url_path,
            'query_string': query_string,
            'headers': list((k.lower().encode(), v.encode()) for k, v in azure_request.headers.items()) if azure_request.headers else [],
            'server': ('localhost', 80),
            'scheme': 'http',
            'root_path': root_path,
            'path_params': path_params,
        }
    
    def _create_starlette_request(self, azure_request, scope: Dict[str, Any], path_params: Dict[str, str]) -> Request:
        """Create a Starlette Request object from Azure Functions request"""
        # This creates a minimal Request-like object for FastAPI
        class MockRequest:
            def __init__(self, azure_req, scope_dict, path_params_dict):
                self.method = azure_req.method.upper() if hasattr(azure_req.method, 'upper') else str(azure_req.method).upper()
                self.url = str(azure_req.url) if hasattr(azure_req.url, '__str__') else azure_req.url
                self.headers = Headers(azure_req.headers if azure_req.headers else {})
                # Handle query_params from Starlette Request or Azure Functions params
                if hasattr(azure_req, 'query_params'):
                    self.query_params = azure_req.query_params
                elif hasattr(azure_req, 'params'):
                    self.query_params = QueryParams(azure_req.params if azure_req.params else {})
                else:
                    self.query_params = QueryParams({})
                self.path_params = path_params_dict
                self.scope = scope_dict
                
                # Store reference to original request for lazy body loading
                self._azure_req = azure_req
                self._body_cache = None
            
            async def body(self):
                """Lazily load and cache the request body"""
                if self._body_cache is not None:
                    return self._body_cache
                
                # Handle different request types
                if hasattr(self._azure_req, 'get_body'):
                    # Azure Functions RPC request
                    self._body_cache = self._azure_req.get_body()
                elif hasattr(self._azure_req, 'body'):
                    # Starlette Request - body() is async
                    if callable(self._azure_req.body):
                        self._body_cache = await self._azure_req.body()
                    else:
                        self._body_cache = self._azure_req.body
                else:
                    self._body_cache = b''
                
                return self._body_cache
            
            async def json(self):
                """Parse body as JSON"""
                body_data = await self.body()
                return json.loads(body_data) if body_data else {}
        
        return MockRequest(azure_request, scope, path_params)
    
    async def _build_handler_kwargs(
        self, 
        route_handler: typing.Callable, 
        request: Any,
        path_params: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Build kwargs for the route handler by inspecting its signature.
        This handles path parameters, query parameters, and Request dependencies.
        """
        import inspect
        
        kwargs = {}
        sig = inspect.signature(route_handler)
        
        for param_name, param in sig.parameters.items():
            # Check if this is a path parameter
            if param_name in path_params:
                # Convert to the correct type if annotation is provided
                value = path_params[param_name]
                if param.annotation != inspect.Parameter.empty:
                    try:
                        # Try to convert to the annotated type (e.g., int, str)
                        if param.annotation == int:
                            value = int(value)
                        elif param.annotation == float:
                            value = float(value)
                        elif param.annotation == bool:
                            value = value.lower() in ('true', '1', 'yes')
                    except (ValueError, AttributeError):
                        pass  # Keep as string if conversion fails
                kwargs[param_name] = value
            
            # Check if this is a query parameter
            elif param_name in request.query_params:
                value = request.query_params[param_name]
                if param.annotation != inspect.Parameter.empty:
                    try:
                        if param.annotation == int:
                            value = int(value)
                        elif param.annotation == float:
                            value = float(value)
                        elif param.annotation == bool:
                            value = value.lower() in ('true', '1', 'yes')
                    except (ValueError, AttributeError):
                        pass
                kwargs[param_name] = value
            
            # Check if parameter expects the Request object
            elif param.annotation == Request or (hasattr(param.annotation, '__name__') and param.annotation.__name__ == 'Request'):
                kwargs[param_name] = request
            
            # Use default value if available and no value provided
            elif param.default != inspect.Parameter.empty:
                # Don't add to kwargs, let Python use the default
                pass
            
        return kwargs
    
    def _format_response(self, result: Any) -> Dict[str, Any]:
        """
        Format FastAPI response to Azure Functions response format
        
        Handles various FastAPI return types:
        - Dict/List: JSON response
        - String: Text response
        - FastAPI Response objects: Extract status, headers, body
        """
        # If result is already a dict with status_code, assume it's formatted
        if isinstance(result, dict) and 'status_code' in result:
            return result
        
        # Handle FastAPI Response objects
        if hasattr(result, 'status_code'):
            body = result.body if hasattr(result, 'body') else ''
            if isinstance(body, bytes):
                body = body.decode('utf-8')
            
            return {
                'status_code': result.status_code,
                'headers': dict(result.headers) if hasattr(result, 'headers') else {},
                'body': body
            }
        
        # Handle dict/list - return as JSON
        if isinstance(result, (dict, list)):
            return {
                'status_code': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(result)
            }
        
        # Handle string
        if isinstance(result, str):
            return {
                'status_code': 200,
                'headers': {'Content-Type': 'text/plain'},
                'body': result
            }
        
        # Default: convert to string
        return {
            'status_code': 200,
            'headers': {'Content-Type': 'text/plain'},
            'body': str(result)
        }


async def execute_fastapi_route(
    app: FastAPI,
    azure_request,
    route_handler: typing.Callable,
    route_path: str,
    is_async: bool
) -> Dict[str, Any]:
    """
    Execute a FastAPI route in response to an Azure Functions invocation
    
    This is the main entry point called by the proxy worker during function invocation
    """
    handler = FastAPIHandler(app)
    return await handler.handle_request(azure_request, route_handler, route_path, is_async)
