"""GRPC client.

Implements loading and execution of Python workers.
"""

import asyncio
import concurrent.futures
import logging
import queue
import threading
import traceback

import grpc

from . import bindings
from . import functions
from . import loader
from . import protos


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
                 grpc_connect_timeout, grpc_max_msg_len):
        self._loop = loop
        self._host = host
        self._port = port
        self._request_id = request_id
        self._worker_id = worker_id
        self._functions = functions.Registry()

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
        self._grpc_max_msg_len = grpc_max_msg_len
        self._grpc_resp_queue: queue.Queue = queue.Queue()
        self._grpc_connected_fut = loop.create_future()
        self._grpc_thread = threading.Thread(
            name='grpc-thread', target=self.__poll_grpc)

        self._logger = logging.getLogger('azure.functions_worker')

    @classmethod
    async def connect(cls, host, port, worker_id, request_id,
                      connect_timeout, max_msg_len=None):
        loop = asyncio._get_running_loop()
        disp = cls(loop, host, port, worker_id, request_id,
                   connect_timeout, max_msg_len)
        disp._grpc_thread.start()
        await disp._grpc_connected_fut
        return disp

    async def dispatch_forever(self):
        if DispatcherMeta.__current_dispatcher__ is not None:
            raise RuntimeError(
                'there can be only one running dispatcher per process')

        self._old_task_factory = self._loop.get_task_factory()

        loader.install()

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
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(logging_handler)
            try:
                await forever
            finally:
                root_logger.removeHandler(logging_handler)
        finally:
            DispatcherMeta.__current_dispatcher__ = None

            loader.uninstall()

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

    def _on_logging(self, record: logging.LogRecord, formatted_msg: str):
        if record.levelno >= logging.CRITICAL:
            log_level = protos.RpcLog.Critical
        elif record.levelno >= logging.ERROR:
            log_level = protos.RpcLog.Error
        elif record.levelno >= logging.WARNING:
            log_level = protos.RpcLog.Warning
        elif record.levelno >= logging.INFO:
            log_level = protos.RpcLog.Information
        elif record.levelno >= logging.DEBUG:
            log_level = protos.RpcLog.Debug
        else:
            log_level = getattr(protos.RpcLog, 'None')

        log = dict(
            level=log_level,
            message=formatted_msg,
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

    async def _dispatch_grpc_request(self, request):
        content_type = request.WhichOneof('content')
        request_handler = getattr(self, f'_handle__{content_type}', None)
        if request_handler is None:
            # Don't crash on unknown messages.  Some of them can be ignored;
            # and if something goes really wrong the host can always just
            # kill the worker's process.
            self._logger.error(
                f'unknown StreamingMessage content type {content_type}')
            return

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
                func_request.metadata.script_file,
                func_request.metadata.entry_point)

            self._functions.add_function(
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
        assert isinstance(current_task, ContextEnabledTask)
        current_task.set_azure_invocation_id(invocation_id)

        try:
            fi: functions.FunctionInfo = self._functions.get_function(
                function_id)

            args = {}
            for pb in invoc_request.input_data:
                pb_type_info = fi.input_types[pb.name]
                if bindings.is_trigger_binding(pb_type_info.binding_name):
                    trigger_metadata = invoc_request.trigger_metadata
                else:
                    trigger_metadata = None
                args[pb.name] = bindings.from_incoming_proto(
                    pb_type_info.binding_name, pb.data,
                    trigger_metadata=trigger_metadata,
                    pytype=pb_type_info.pytype)

            if fi.requires_context:
                args['context'] = bindings.Context(
                    fi.name, fi.directory, invocation_id)

            if fi.output_types:
                for name in fi.output_types:
                    args[name] = bindings.Out()

            if fi.is_async:
                call_result = await fi.func(**args)
            else:
                call_result = await self._loop.run_in_executor(
                    self._sync_call_tp,
                    self.__run_sync_func, invocation_id, fi.func, args)

            if call_result is not None and not fi.has_return:
                raise RuntimeError(
                    f'function {fi.name!r} without a $return binding '
                    f'returned a non-None value')

            output_data = []
            if fi.output_types:
                for out_name, out_type_info in fi.output_types.items():
                    val = args[name].get()
                    if val is None:
                        # TODO: is the "Out" parameter optional?
                        # Can "None" be marshaled into protos.TypedData?
                        continue

                    rpc_val = bindings.to_outgoing_proto(
                        out_type_info.binding_name, val,
                        pytype=out_type_info.pytype)
                    assert rpc_val is not None

                    output_data.append(
                        protos.ParameterBinding(
                            name=name,
                            data=rpc_val))

            return_value = None
            if fi.return_type is not None:
                return_value = bindings.to_outgoing_proto(
                    fi.return_type.binding_name, call_result,
                    pytype=fi.return_type.pytype)

            return protos.StreamingMessage(
                request_id=self.request_id,
                invocation_response=protos.InvocationResponse(
                    invocation_id=invocation_id,
                    return_value=return_value,
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
        options = []
        if self._grpc_max_msg_len:
            options.append(('grpc.max_receive_message_length',
                            self._grpc_max_msg_len))
            options.append(('grpc.max_send_message_length',
                            self._grpc_max_msg_len))

        channel = grpc.insecure_channel(
            f'{self._host}:{self._port}', options)

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
        msg = self.format(record)
        Dispatcher.current._on_logging(record, msg)


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
