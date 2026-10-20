# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
HTTP v2 Streaming Support for FastAPI Runtime

This module provides HTTP streaming capabilities, allowing the Azure Functions
host to communicate with the worker via HTTP rather than gRPC for HTTP-triggered
functions. This enables streaming responses and better performance for FastAPI apps.
"""
import abc
import asyncio
import socket
from typing import Any, Dict

from .logging import logger
from .utils.constants import X_MS_INVOCATION_ID


# Http V2 Exceptions
class HttpServerInitError(Exception):
    """Exception raised when there is an error during HTTP server initialization."""


class MissingHeaderError(ValueError):
    """Exception raised when a required header is missing in the HTTP request."""


class BaseContextReference(abc.ABC):
    """
    Base class for context references.
    Stores HTTP request/response pairs for each invocation.
    """
    def __init__(self, event_class, http_request=None, http_response=None,
                 function=None, fi_context=None, args=None,
                 http_trigger_param_name=None):
        self._http_request = http_request
        self._http_response = http_response
        self._function = function
        self._fi_context = fi_context
        self._args = args
        self._http_trigger_param_name = http_trigger_param_name
        self._http_request_available_event = event_class()
        self._http_response_available_event = event_class()

    @property
    def http_request(self):
        return self._http_request

    @http_request.setter
    def http_request(self, value):
        self._http_request = value
        self._http_request_available_event.set()

    @property
    def http_response(self):
        return self._http_response

    @http_response.setter
    def http_response(self, value):
        self._http_response = value
        self._http_response_available_event.set()

    @property
    def function(self):
        return self._function

    @function.setter
    def function(self, value):
        self._function = value

    @property
    def fi_context(self):
        return self._fi_context

    @fi_context.setter
    def fi_context(self, value):
        self._fi_context = value

    @property
    def http_trigger_param_name(self):
        return self._http_trigger_param_name

    @http_trigger_param_name.setter
    def http_trigger_param_name(self, value):
        self._http_trigger_param_name = value

    @property
    def args(self):
        return self._args

    @args.setter
    def args(self, value):
        self._args = value

    @property
    def http_request_available_event(self):
        return self._http_request_available_event

    @property
    def http_response_available_event(self):
        return self._http_response_available_event


class AsyncContextReference(BaseContextReference):
    """
    Asynchronous context reference class.
    """
    def __init__(self, http_request=None, http_response=None, function=None,
                 fi_context=None, args=None):
        super().__init__(event_class=asyncio.Event, http_request=http_request,
                         http_response=http_response,
                         function=function, fi_context=fi_context, args=args)
        self.is_async = True


class SingletonMeta(type):
    """
    Metaclass for implementing the singleton pattern.
    """
    _instances: Dict[Any, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class HttpCoordinator(metaclass=SingletonMeta):
    """
    HTTP coordinator class for managing HTTP v2 requests and responses.
    
    This coordinates between the HTTP server receiving requests and the
    invocation handler processing them.
    """
    def __init__(self):
        self._context_references: Dict[str, BaseContextReference] = {}

    def set_http_request(self, invoc_id, http_request):
        if invoc_id not in self._context_references:
            self._context_references[invoc_id] = AsyncContextReference()
        context_ref = self._context_references.get(invoc_id)
        context_ref.http_request = http_request

    def set_http_response(self, invoc_id, http_response):
        if invoc_id not in self._context_references:
            raise KeyError("No context reference found for invocation %s" % invoc_id)
        context_ref = self._context_references.get(invoc_id)
        context_ref.http_response = http_response

    async def get_http_request_async(self, invoc_id):
        if invoc_id not in self._context_references:
            self._context_references[invoc_id] = AsyncContextReference()

        await self._context_references.get(invoc_id).http_request_available_event.wait()
        return self._pop_http_request(invoc_id)

    async def await_http_response_async(self, invoc_id):
        if invoc_id not in self._context_references:
            raise KeyError("No context reference found for invocation %s" % invoc_id)

        await self._context_references.get(invoc_id).http_response_available_event.wait()
        return self._pop_http_response(invoc_id)

    def _pop_http_request(self, invoc_id):
        context_ref = self._context_references.get(invoc_id)
        request = context_ref.http_request
        if request is not None:
            context_ref.http_request = None
            return request

        raise ValueError("No http request found for invocation %s" % invoc_id)

    def _pop_http_response(self, invoc_id):
        context_ref = self._context_references.pop(invoc_id, None)
        if context_ref is None:
            raise KeyError(
                "No context reference found for invocation %s" % invoc_id)

        response = context_ref.http_response
        if response is not None:
            return response

        raise ValueError("No http response found for invocation %s" % invoc_id)


def get_unused_tcp_port():
    """Find an unused TCP port for the HTTP server"""
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind(("", 0))
    port = tcp_socket.getsockname()[1]
    tcp_socket.close()
    return port


async def initialize_http_server(host_addr: str, fastapi_app) -> str:
    """
    Initialize HTTP v2 server for handling HTTP streaming requests.
    
    This creates a simple HTTP server using Starlette (FastAPI's underlying framework)
    that receives HTTP requests from the Azure Functions host and coordinates with
    the invocation handler to process them.
    
    Args:
        host_addr: The host address to bind to (e.g., "127.0.0.1")
        fastapi_app: The user's FastAPI application instance
        
    Returns:
        The URL of the HTTP server (e.g., "http://127.0.0.1:8080")
    """
    try:
        from starlette.applications import Starlette
        from starlette.responses import Response, JSONResponse
        from starlette.routing import Route
        import uvicorn
        
        unused_port = get_unused_tcp_port()
        
        async def catch_all(request):
            """
            Catch-all route that receives HTTP requests from the Azure Functions host.
            
            The request includes the invocation ID in the X-MS-INVOCATION-ID header.
            We store the request and wait for the invocation handler to process it,
            then return the response.
            """
            invoc_id = request.headers.get(X_MS_INVOCATION_ID)
            if invoc_id is None:
                raise MissingHeaderError("Header %s not found" % X_MS_INVOCATION_ID)
            
            logger.info('HTTP streaming: Received HTTP request for invocation %s', invoc_id)
            http_coordinator.set_http_request(invoc_id, request)
            
            # Wait for the invocation handler to process and set the response
            http_resp = await http_coordinator.await_http_response_async(invoc_id)

            logger.info('HTTP streaming: Sending HTTP response for invocation %s', invoc_id)
            
            # If http_resp is an exception, raise it
            if isinstance(http_resp, Exception):
                raise http_resp

            return http_resp
        
        # Create a Starlette app with a catch-all route
        streaming_app = Starlette(
            routes=[
                Route("/{path:path}", catch_all, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]),
            ]
        )
        
        # Configure Uvicorn server
        config = uvicorn.Config(
            app=streaming_app,
            host=host_addr,
            port=unused_port,
            log_level="info",
            access_log=False,
        )
        server = uvicorn.Server(config)
        
        # Run server in background
        loop = asyncio.get_event_loop()
        loop.create_task(server.serve())
        
        web_server_address = f"http://{host_addr}:{unused_port}"
        logger.info('HTTP streaming server starting on %s', web_server_address)

        return web_server_address

    except Exception as e:
        raise HttpServerInitError("Error initializing HTTP server: %s" % e) from e


class HttpV2Registry:
    """
    HTTP v2 registry class for managing HTTP v2 streaming state.
    
    For FastAPI runtime, we always enable HTTP streaming by default.
    """
    _http_v2_enabled = True  # Always enabled for FastAPI runtime
    _http_v2_enabled_checked = True

    @classmethod
    def http_v2_enabled(cls, **kwargs):
        """Check if HTTP v2 streaming is enabled (always True for FastAPI)"""
        logger.debug("HTTP streaming enabled: %s", cls._http_v2_enabled)
        return cls._http_v2_enabled
    
    @classmethod
    def set_http_v2_enabled(cls, enabled: bool):
        """Allow programmatic enabling/disabling of HTTP streaming"""
        cls._http_v2_enabled = enabled
        logger.info("HTTP streaming set to: %s", enabled)


# Global singleton instance
http_coordinator = HttpCoordinator()

