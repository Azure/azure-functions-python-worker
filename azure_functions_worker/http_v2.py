import abc
import asyncio
import socket
from typing import Dict


class BaseContextReference(abc.ABC):
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
    def __init__(self, http_request=None, http_response=None, function=None,
                 fi_context=None, args=None):
        super().__init__(event_class=asyncio.Event, http_request=http_request,
                         http_response=http_response,
                         function=function, fi_context=fi_context, args=args)
        self.is_async = True


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class HttpCoordinator(metaclass=SingletonMeta):
    def __init__(self):
        self._context_references: Dict[str, BaseContextReference] = {}

    def set_http_request(self, invoc_id, http_request):
        if invoc_id not in self._context_references:
            self._context_references[invoc_id] = AsyncContextReference()
        context_ref = self._context_references.get(invoc_id)
        context_ref.http_request = http_request

    def set_http_response(self, invoc_id, http_response):
        if invoc_id not in self._context_references:
            raise Exception("No context reference found for invocation %s",
                            invoc_id)
        context_ref = self._context_references.get(invoc_id)
        context_ref.http_response = http_response

    async def get_http_request_async(self, invoc_id):
        if invoc_id not in self._context_references:
            self._context_references[invoc_id] = AsyncContextReference()

        await asyncio.sleep(0)
        await self._context_references.get(
            invoc_id).http_request_available_event.wait()
        return self._pop_http_request(invoc_id)

    async def await_http_response_async(self, invoc_id):
        if invoc_id not in self._context_references:
            raise Exception("No context reference found for invocation %s",
                            invoc_id)
        await asyncio.sleep(0)
        await self._context_references.get(
            invoc_id).http_response_available_event.wait()
        return self._pop_http_response(invoc_id)

    def _pop_http_request(self, invoc_id):
        context_ref = self._context_references.get(invoc_id)
        request = context_ref.http_request
        if request is not None:
            context_ref.http_request = None
            return request

        raise Exception("No http request found for invocation %s", invoc_id)

    def _pop_http_response(self, invoc_id):
        context_ref = self._context_references.get(invoc_id)
        response = context_ref.http_response
        if response is not None:
            context_ref.http_response = None
            return response
        raise Exception("No http response found for invocation %s", invoc_id)


def get_unused_tcp_port():
    # Create a TCP socket
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind it to a free port provided by the OS
    tcp_socket.bind(("", 0))
    # Get the port number
    port = tcp_socket.getsockname()[1]
    # Close the socket
    tcp_socket.close()
    # Return the port number
    return port


http_coordinator = HttpCoordinator()
