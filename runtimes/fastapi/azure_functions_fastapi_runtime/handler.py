# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
FastAPI Request/Response Handler
Handles execution of FastAPI routes and conversion between Azure Functions and ASGI
"""
import asyncio
import json
import typing
from typing import Any, Dict, List, Optional
from io import BytesIO

from fastapi import FastAPI


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
            route_path: The route path pattern
            is_async: Whether the handler is async
            
        Returns:
            Dict with status_code, headers, and body for Azure Functions response
        """
        try:
            # Build ASGI-like scope from Azure Functions request
            scope = self._build_scope(azure_request, route_path)
            
            # For now, we'll do a simplified execution
            # In a full implementation, this would go through ASGI protocol
            
            # Extract route parameters from URL if present
            route_params = getattr(azure_request, 'route_params', {})
            
            # Build kwargs for the handler
            kwargs = {}
            
            # Add route parameters
            kwargs.update(route_params)
            
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
    
    def _build_scope(self, azure_request, route_path: str) -> Dict[str, Any]:
        """Build ASGI scope from Azure Functions request"""
        return {
            'type': 'http',
            'method': azure_request.method,
            'path': azure_request.url,
            'query_string': azure_request.query_string if hasattr(azure_request, 'query_string') else b'',
            'headers': list((k.encode(), v.encode()) for k, v in azure_request.headers.items()) if azure_request.headers else [],
            'server': ('localhost', 80),
            'scheme': 'http',
        }
    
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
