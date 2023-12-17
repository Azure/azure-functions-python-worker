import abc
import asyncio
from typing import Dict
from .logging import logger


class BaseContextReference(abc.ABC):
    def __init__(self, event_class, http_request=None, http_response=None, function=None, fi_context=None, args=None, http_trigger_param_name=None):
        self._http_request = http_request
        self._http_response = http_response
        self._function = function
        self._fi_context = fi_context
        self._args = args
        self._http_trigger_param_name = http_trigger_param_name
        self._http_request_available_event = event_class()
        self._http_response_available_event = event_class()
        self._rpc_invocation_ready_event = event_class()

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

    @property
    def rpc_invocation_ready_event(self):
        return self._rpc_invocation_ready_event


class AsyncContextReference(BaseContextReference):
    def __init__(self, http_request=None, http_response=None, function=None, fi_context=None, args=None):
        super().__init__(event_class=asyncio.Event, http_request=http_request, http_response=http_response,
                         function=function, fi_context=fi_context, args=args)
        self.is_async = True


class HttpCoordinator:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HttpCoordinator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._context_references: Dict[str, BaseContextReference] = {}
            self._initialized = True
        
    def set_http_request(self, invoc_id, http_request):
        if invoc_id not in self._context_references:
            self._context_references[invoc_id] = AsyncContextReference()
        context_ref = self._context_references.get(invoc_id)
        context_ref.http_request = http_request
        context_ref.http_request_available_event.set()

    def set_http_response(self, invoc_id, http_response):
        context_ref = self._context_references.get(invoc_id)
        context_ref.http_response = http_response
        context_ref.http_response_available_event.set()

    async def await_http_request_async(self, invoc_id):
        if invoc_id not in self._context_references:
            self._context_references[invoc_id] = AsyncContextReference()
        await self._context_references.get(invoc_id).http_request_available_event.wait()
        return self._pop_http_request(invoc_id)

    async def await_http_response_async(self, invoc_id):
        logger.info("-----> http waiting for invoc res %s", invoc_id)
        await self._context_references.get(invoc_id).http_response_available_event.wait()
        return self._pop_http_response(invoc_id)
    
    def _pop_http_request(self, invoc_id):
        context_ref = self._context_references.get(invoc_id)
        request = context_ref.http_request
        if request is not None:
            context_ref.http_request = None
            logger.info("-----> grpc got invoc req %s", invoc_id)
            return request
        
        raise Exception("-----> No request found for invoc %s", invoc_id)

    def _pop_http_response(self, invoc_id):
        context_ref = self._context_references.get(invoc_id)
        response = context_ref.http_response
        if response is not None:
            context_ref.http_response = None
            logger.info("-----> grpc got invoc res %s", invoc_id)
            return response
        
        raise Exception("-----> No response found for invoc %s", invoc_id)


http_coordinator = HttpCoordinator()
