"""GRPC client.

Implements loading and execution of Python workers.
"""

import asyncio
import concurrent.futures
import inspect
import logging
import queue
import threading
import typing
import traceback

import azure.functions as azf
import grpc

from . import loader
from . import protos
from . import rpc_types


class FunctionInfo(typing.NamedTuple):

    func: object
    sig: inspect.Signature
    name: str
    directory: str
    outputs: typing.Set[str]
    requires_context: bool
    is_async: bool


class DispatcherMeta(type):

    __current_dispatcher__ = None

    @property
    def current(mcls):
        disp = mcls.__current_dispatcher__
        if disp is None:
            raise RuntimeError('no currently running Dispatcher is found')
        return disp


class Dispatcher(metaclass=DispatcherMeta):

    _GRPC_STOP_RESPONSE = object()

    def __init__(self, loop, host, port, worker_id, request_id,
                 grpc_connect_timeout):
        self._loop = loop
        self._host = host
        self._port = port
        self._request_id = request_id
        self._worker_id = worker_id
        self._functions = {}

        # A thread-pool for synchronous function calls.  We limit
        # the number of threads to 1 so that one Python worker can
        # only run one synchronous function in parallel.  This is
        # because synchronous code in Python is rarely designed with
        # concurrency in mind, so we don't want to allow users to
        # have races in their synchronous functions.  Moreover,
        # because of the GIL in CPython, it rarely makes sense to
        # use threads (unless the code is IO bound, but we have
        # async support for that.)
        self._sync_call_tp = concurrent.futures.ThreadPoolExecutor(
            max_workers=1)

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
        if DispatcherMeta.__current_dispatcher__ is not None:
            raise RuntimeError(
                'there can be only one running dispatcher per process')

        self._old_task_factory = self._loop.get_task_factory()
        DispatcherMeta.__current_dispatcher__ = self
        try:
            forever = self._loop.create_future()

            self._grpc_resp_queue.put_nowait(
                protos.StreamingMessage(
                    request_id=self.request_id,
                    start_stream=protos.StartStream(
                        worker_id=self.worker_id)))

            self._loop.set_task_factory(
                lambda loop, coro: ContextEnabledTask(coro, loop=loop))

            logging_handler = AsyncLoggingHandler()
            root_logger = logging.getLogger()
            root_logger.addHandler(logging_handler)
            try:
                await forever
            finally:
                root_logger.removeHandler(logging_handler)
        finally:
            DispatcherMeta.__current_dispatcher__ = None
            self._loop.set_task_factory(self._old_task_factory)
            self.stop()

    def stop(self):
        if self._grpc_thread is not None:
            self._grpc_resp_queue.put_nowait(self._GRPC_STOP_RESPONSE)
            self._grpc_thread.join()
            self._grpc_thread = None

        if self._sync_call_tp is not None:
            self._sync_call_tp.shutdown()
            self._sync_call_tp = None

    def _on_logging(self, record: logging.LogRecord):
        if record.levelno >= logging.CRITICAL:
            log_level = protos.RpcLog.Critical
        elif record.levelno >= logging.ERROR:
            log_level = protos.RpcLog.Error
        elif record.levelno >= logging.WARNING:
            log_level = protos.RpcLog.Warning
        elif record.levelno >= logging.INFO:
            log_level = protos.RpcLog.Info
        elif record.levelno >= logging.DEBUG:
            log_level = protos.RpcLog.Debug
        else:
            log_level = getattr(protos.RpcLog, 'None')

        log = dict(
            level=log_level,
            message=record.msg,
            category=record.name,
        )

        invocation_id = get_current_invocation_id()
        if invocation_id is not None:
            log['invocation_id'] = invocation_id

        # XXX: When an exception field is set in RpcLog, WebHost doesn't
        # wait for the call result and simply aborts the execution.
        #
        # if record.exc_info and record.exc_info[1] is not None:
        #     log['exception'] = self._serialize_exception(record.exc_info[1])

        self._grpc_resp_queue.put_nowait(
            protos.StreamingMessage(
                request_id=self.request_id,
                rpc_log=protos.RpcLog(**log)))

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

    def _register_function(self, function_id: str, func: callable,
                           metadata: protos.RpcFunctionMetadata):
        func_name = metadata.name
        sig = inspect.signature(func)
        params = sig.parameters.copy()

        outputs = set()
        requires_context = False

        bindings = {}
        return_binding = None
        for name, desc in metadata.bindings.items():
            if desc.direction == protos.BindingInfo.inout:
                raise TypeError(
                    f'cannot load the {func_name} function: '
                    f'"inout" bindings are not supported')

            if name == '$return':
                # TODO:
                # *  add proper gRPC->Python type reflection;
                # * convert the type from function.json to a Python type;
                # * enforce return type of a function call in Python;
                # * use the return type information to marshal the result into
                #   a correct gRPC type.

                if desc.direction != protos.BindingInfo.out:
                    raise TypeError(
                        f'cannot load the {func_name} function: '
                        f'"$return" binding must have direction set to "out"')

                return_binding = desc  # NoQA
            else:
                bindings[name] = desc

        if 'context' in params and 'context' not in bindings:
            requires_context = True
            ctx_param = params.pop('context')
            if ctx_param.annotation is not ctx_param.empty:
                if (not isinstance(ctx_param.annotation, type) or
                        not issubclass(ctx_param.annotation, azf.Context)):
                    raise TypeError(
                        f'cannot load the {func_name} function: '
                        f'the "context" parameter is expected to be of '
                        f'type azure.functions.Context, got '
                        f'{ctx_param.annotation!r}')

        if set(params) - set(bindings):
            raise RuntimeError(
                f'cannot load the {func_name} function: '
                f'the following parameters are declared in Python but '
                f'not in function.json: {set(params) - set(bindings)!r}')

        if set(bindings) - set(params):
            raise RuntimeError(
                f'cannot load the {func_name} function: '
                f'the following parameters are declared in function.json but '
                f'not in Python: {set(bindings) - set(params)!r}')

        for param in params.values():
            desc = bindings[param.name]

            param_has_anno = param.annotation is not param.empty
            is_param_out = (param_has_anno and
                            issubclass(param.annotation, azf.Out))
            is_binding_out = desc.direction == protos.BindingInfo.out

            if is_binding_out and param_has_anno and not is_param_out:
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'binding {param.name} is declared to have the "out" '
                    f'direction, but its annotation in Python is not '
                    f'a subclass of azure.functions.Out')

            if not is_binding_out and is_param_out:
                raise RuntimeError(
                    f'cannot load the {func_name} function: '
                    f'binding {param.name} is declared to have the "in" '
                    f'direction in function.json, but its annotation '
                    f'is azure.functions.Out in Python')

            if is_binding_out:
                outputs.add(param.name)

        self._functions[function_id] = FunctionInfo(
            func=func,
            sig=sig,
            name=func_name,
            directory=metadata.directory,
            outputs=frozenset(outputs),
            requires_context=requires_context,
            is_async=inspect.iscoroutinefunction(func))

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

            self._register_function(
                function_id, func, func_request.metadata)

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

        # Set the current `invocation_id` to the current task so
        # that our logging handler can find it.
        current_task = asyncio.Task.current_task(self._loop)
        current_task.set_azure_invocation_id(invocation_id)

        try:
            try:
                fi: FunctionInfo = self._functions[function_id]
            except KeyError:
                raise RuntimeError(
                    f'unknown function id {function_id}') from None

            params = {}
            for pb in invoc_request.input_data:
                params[pb.name] = rpc_types.from_incoming_proto(pb.data)

            if fi.requires_context:
                params['context'] = rpc_types.Context(
                    fi.name, fi.directory, invocation_id)

            if fi.outputs:
                for name in fi.outputs:
                    params[name] = rpc_types.Out()

            if fi.is_async:
                call_result = await fi.func(**params)
            else:
                call_result = await self._loop.run_in_executor(
                    self._sync_call_tp,
                    self.__run_sync_func, invocation_id, fi.func, params)

            output_data = []
            if fi.outputs:
                for name in fi.outputs:
                    rpc_val = rpc_types.to_outgoing_proto(params[name].get())
                    if rpc_val is None:
                        # TODO: is the "Out" parameter optional?
                        # Can "None" be marshaled into protos.TypedData?
                        continue
                    output_data.append(
                        protos.ParameterBinding(
                            name=name,
                            data=rpc_val))

            return protos.StreamingMessage(
                request_id=self.request_id,
                invocation_response=protos.InvocationResponse(
                    invocation_id=invocation_id,
                    return_value=rpc_types.to_outgoing_proto(call_result),
                    result=protos.StatusResult(
                        status=protos.StatusResult.Success),
                    output_data=output_data))

        except Exception as ex:
            return protos.StreamingMessage(
                request_id=self.request_id,
                invocation_response=protos.InvocationResponse(
                    invocation_id=invocation_id,
                    result=protos.StatusResult(
                        status=protos.StatusResult.Failure,
                        exception=self._serialize_exception(ex))))

    def __run_sync_func(self, invocation_id, func, params):
        # This helper exists because we need to access the current
        # invocation_id from ThreadPoolExecutor's threads.
        _invocation_id_local.v = invocation_id
        try:
            return func(**params)
        finally:
            _invocation_id_local.v = None

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
                    grpc_req_stream.cancel()
                    return
                yield msg

        grpc_req_stream = stub.EventStream(gen(self._grpc_resp_queue))
        try:
            for req in grpc_req_stream:
                self._loop.call_soon_threadsafe(
                    self._loop.create_task, self._dispatch_grpc_request(req))
        except Exception as ex:
            if ex is grpc_req_stream:
                # Yes, this is how grpc_req_stream iterator exits.
                return
            raise


class AsyncLoggingHandler(logging.Handler):

    def emit(self, record):
        Dispatcher.current._on_logging(record)


class ContextEnabledTask(asyncio.Task):

    _AZURE_INVOCATION_ID = '__azure_function_invocation_id__'

    def __init__(self, coro, loop):
        super().__init__(coro, loop=loop)

        current_task = asyncio.Task.current_task(loop)
        if current_task is not None:
            invocation_id = getattr(
                current_task, self._AZURE_INVOCATION_ID, None)
            if invocation_id is not None:
                self.set_azure_invocation_id(invocation_id)

    def set_azure_invocation_id(self, invocation_id):
        setattr(self, self._AZURE_INVOCATION_ID, invocation_id)


def get_current_invocation_id():
    loop = asyncio._get_running_loop()
    if loop is not None:
        current_task = asyncio.Task.current_task(loop)
        if current_task is not None:
            return getattr(
                current_task, ContextEnabledTask._AZURE_INVOCATION_ID, None)

    return getattr(_invocation_id_local, 'v', None)


_invocation_id_local = threading.local()
