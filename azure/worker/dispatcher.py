"""GRPC client.

Implements loading and execution of Python workers.
"""

import asyncio
import inspect
import queue
import threading
import typing
import traceback

import grpc

from . import bind
from . import loader
from . import protos
from . import types


class FunctionInfo(typing.NamedTuple):

    func: object
    name: str
    directory: str


class Dispatcher:

    _GRPC_STOP_RESPONSE = object()

    def __init__(self, loop, host, port, worker_id, request_id,
                 grpc_connect_timeout):
        self._loop = loop
        self._host = host
        self._port = port
        self._request_id = request_id
        self._worker_id = worker_id
        self._functions = {}

        self._grpc_connect_timeout = grpc_connect_timeout
        self._grpc_resp_queue = queue.Queue()
        self._grpc_connected_fut = loop.create_future()
        self._grpc_thread = threading.Thread(
            name='grpc-thread', target=self.__poll_grpc)

    @classmethod
    async def connect(cls, host, port, worker_id, request_id,
                      connect_timeout):
        loop = asyncio._get_running_loop()
        disp = cls(loop, host, port, worker_id, request_id, connect_timeout)
        disp._grpc_thread.start()
        await disp._grpc_connected_fut
        return disp

    async def dispatch_forever(self):
        forever = self._loop.create_future()

        self._grpc_resp_queue.put_nowait(
            protos.StreamingMessage(
                request_id=self.request_id,
                start_stream=protos.StartStream(
                    worker_id=self.worker_id)))

        try:
            await forever
        finally:
            self.stop()

    def stop(self):
        if self._grpc_thread is not None:
            self._grpc_resp_queue.put_nowait(self._GRPC_STOP_RESPONSE)
            self._grpc_thread.join()
            self._grpc_thread = None

    @property
    def request_id(self):
        return self._request_id

    @property
    def worker_id(self):
        return self._worker_id

    def _serialize_exception(self, exc):
        return protos.RpcException(
            message=f'{type(exc).__name__}: {exc.args[0]}',
            stack_trace=''.join(traceback.format_tb(exc.__traceback__)))

    async def _dispatch_grpc_request(self, request):
        content_type = request.WhichOneof('content')
        request_handler = getattr(self, f'_handle__{content_type}', None)
        if request_handler is None:
            raise RuntimeError(
                f'unknown StreamingMessage content type {content_type}')

        resp = await request_handler(request)
        self._grpc_resp_queue.put_nowait(resp)

    async def _handle__worker_init_request(self, req):
        return protos.StreamingMessage(
            request_id=self.request_id,
            worker_init_response=protos.WorkerInitResponse(
                result=protos.StatusResult(
                    status=protos.StatusResult.Success)))

    async def _handle__function_load_request(self, req):
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
                        exception=self._serialize_exception(ex))))

    async def _handle__invocation_request(self, req):
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

            if inspect.iscoroutine(call_result):
                call_result = await call_result

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
                        exception=self._serialize_exception(ex))))

    def __poll_grpc(self):
        channel = grpc.insecure_channel(f'{self._host}:{self._port}')

        try:
            grpc.channel_ready_future(channel).result(
                timeout=self._grpc_connect_timeout)
        except Exception as ex:
            self._loop.call_soon_threadsafe(
                self._grpc_connected_fut.set_exception, ex)
            return
        else:
            self._loop.call_soon_threadsafe(
                self._grpc_connected_fut.set_result, True)

        stub = protos.FunctionRpcStub(channel)

        def gen(resp_queue):
            while True:
                msg = resp_queue.get()
                if msg is self._GRPC_STOP_RESPONSE:
                    return
                yield msg

        grpc_req_stream = stub.EventStream(gen(self._grpc_resp_queue))
        for req in grpc_req_stream:
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self._dispatch_grpc_request(req))
