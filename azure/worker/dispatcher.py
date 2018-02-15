"""GRPC client.

Implements loading and execution of Python workers.
"""


import typing
import traceback

from . import bind
from . import loader
from . import protos
from . import types


class FunctionInfo(typing.NamedTuple):
    func: object
    name: str
    directory: str


class Dispatcher:

    def __init__(self, response_queue, request_id):
        self._response_queue = response_queue
        self._request_id = request_id
        self._functions = {}

    @property
    def request_id(self):
        return self._request_id

    def serialize_exception(self, exc):
        return protos.RpcException(
            message=f'{type(exc).__name__}: {exc.args[0]}',
            stack_trace=''.join(traceback.format_tb(exc.__traceback__)))

    def dispatch(self, request):
        content_type = request.WhichOneof('content')
        method = getattr(self, f'handle__{content_type}', None)
        if method is None:
            raise RuntimeError(
                f'unknown StreamingMessage content type {content_type}')

        resp = method(request)
        self._response_queue.put(resp)

    def handle__worker_init_request(self, req):
        return protos.StreamingMessage(
            request_id=self.request_id,
            worker_init_response=protos.WorkerInitResponse(
                result=protos.StatusResult(
                    status=protos.StatusResult.Success)))

    def handle__function_load_request(self, req):
        func_request = req.function_load_request
        function_id = func_request.function_id

        try:
            func = loader.load_function(
                func_request.metadata.name,
                func_request.metadata.directory,
                func_request.metadata.script_file)

            self._functions[function_id] = FunctionInfo(
                func=func,
                name=func_request.metadata.name,
                directory=func_request.metadata.directory)

            return protos.StreamingMessage(
                request_id=self.request_id,
                function_load_response=protos.FunctionLoadResponse(
                    function_id=function_id,
                    result=protos.StatusResult(
                        status=protos.StatusResult.Success)))

        except Exception as ex:
            return protos.StreamingMessage(
                request_id=self.request_id,
                function_load_response=protos.FunctionLoadResponse(
                    function_id=function_id,
                    result=protos.StatusResult(
                        status=protos.StatusResult.Failure,
                        exception=self.serialize_exception(ex))))

    def handle__invocation_request(self, req):
        invoc_request = req.invocation_request

        invocation_id = invoc_request.invocation_id
        function_id = invoc_request.function_id

        try:
            try:
                funcinfo = self._functions[function_id]
            except KeyError:
                raise RuntimeError(
                    f'unknown function id {function_id}') from None

            ctx = types.Context(
                funcinfo.name, funcinfo.directory, invocation_id)

            call_result = bind.call(
                funcinfo.func, ctx, invoc_request.input_data)

            return protos.StreamingMessage(
                request_id=self.request_id,
                invocation_response=protos.InvocationResponse(
                    invocation_id=invocation_id,
                    return_value=types.to_outgoing_proto(call_result),
                    result=protos.StatusResult(
                        status=protos.StatusResult.Success)))

        except Exception as ex:
            return protos.StreamingMessage(
                request_id=self.request_id,
                invocation_response=protos.InvocationResponse(
                    invocation_id=invocation_id,
                    result=protos.StatusResult(
                        status=protos.StatusResult.Failure,
                        exception=self.serialize_exception(ex))))
