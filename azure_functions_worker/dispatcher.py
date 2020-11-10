# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""GRPC client.

Implements loading and execution of Python workers.
"""

import asyncio
import concurrent.futures
import importlib
import inspect
import logging
import os
import queue
import sys
import threading
from asyncio import BaseEventLoop
from logging import LogRecord
from typing import Optional, List

import grpc

from . import bindings
from . import constants
from . import functions
from . import loader
from . import protos
from .constants import (CONSOLE_LOG_PREFIX, PYTHON_THREADPOOL_THREAD_COUNT,
                        PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT,
                        PYTHON_THREADPOOL_THREAD_COUNT_MAX,
                        PYTHON_THREADPOOL_THREAD_COUNT_MIN)
from .logging import disable_console_logging, enable_console_logging
from .logging import error_logger, is_system_log_category, logger
from .utils.common import get_app_setting
from .utils.tracing import marshall_exception_trace
from .utils.wrappers import disable_feature_by

_TRUE = "true"

"""In Python 3.6, the current_task method was in the Task class, but got moved
out in 3.7+ and fully removed in 3.9. Thus, to support 3.6 and 3.9 together, we
need to switch the implementation of current_task for 3.6.
"""
_CURRENT_TASK = asyncio.Task.current_task \
    if (sys.version_info[0] == 3 and sys.version_info[1] == 6) \
    else asyncio.current_task


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

    def __init__(self, loop: BaseEventLoop, host: str, port: int,
                 worker_id: str, request_id: str,
                 grpc_connect_timeout: float,
                 grpc_max_msg_len: int = -1) -> None:
        self._loop = loop
        self._host = host
        self._port = port
        self._request_id = request_id
        self._worker_id = worker_id
        self._functions = functions.Registry()

        self._old_task_factory = None

        # We allow the customer to change synchronous thread pool count by
        # PYTHON_THREADPOOL_THREAD_COUNT app setting. The default value is 1.
        self._sync_tp_max_workers: int = self._get_sync_tp_max_workers()
        self._sync_call_tp: concurrent.futures.Executor = (
            self._create_sync_call_tp(self._sync_tp_max_workers)
        )

        self._grpc_connect_timeout: float = grpc_connect_timeout
        # This is set to -1 by default to remove the limitation on msg size
        self._grpc_max_msg_len: int = grpc_max_msg_len
        self._grpc_resp_queue: queue.Queue = queue.Queue()
        self._grpc_connected_fut = loop.create_future()
        self._grpc_thread: threading.Thread = threading.Thread(
            name='grpc-thread', target=self.__poll_grpc)

    @classmethod
    async def connect(cls, host: str, port: int, worker_id: str,
                      request_id: str, connect_timeout: float):
        loop = asyncio.events.get_event_loop()
        disp = cls(loop, host, port, worker_id, request_id, connect_timeout)
        disp._grpc_thread.start()
        await disp._grpc_connected_fut
        logger.info('Successfully opened gRPC channel to %s:%s ', host, port)
        return disp

    async def dispatch_forever(self):
        if DispatcherMeta.__current_dispatcher__ is not None:
            raise RuntimeError('there can be only one running dispatcher per '
                               'process')

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

            # Detach console logging before enabling GRPC channel logging
            logger.info('Detaching console logging.')
            disable_console_logging()

            # Attach gRPC logging to the root logger. Since gRPC channel is
            # established, should use it for system and user logs
            logging_handler = AsyncLoggingHandler()
            root_logger = logging.getLogger()

            # Don't change this unless you read #780 and #745
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(logging_handler)
            logger.info('Switched to gRPC logging.')
            logging_handler.flush()

            try:
                await forever
            finally:
                logger.warning('Detaching gRPC logging due to exception.')
                logging_handler.flush()
                root_logger.removeHandler(logging_handler)

                # Reenable console logging when there's an exception
                enable_console_logging()
                logger.warning('Switched to console logging due to exception.')
        finally:
            DispatcherMeta.__current_dispatcher__ = None

            loader.uninstall()

            self._loop.set_task_factory(self._old_task_factory)
            self.stop()

    def stop(self) -> None:
        if self._grpc_thread is not None:
            self._grpc_resp_queue.put_nowait(self._GRPC_STOP_RESPONSE)
            self._grpc_thread.join()
            self._grpc_thread = None

        self._stop_sync_call_tp()

    def on_logging(self, record: logging.LogRecord, formatted_msg: str) -> None:
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

        if is_system_log_category(record.name):
            log_category = protos.RpcLog.RpcLogCategory.Value('System')
        else:  # customers using logging will yield 'root' in record.name
            log_category = protos.RpcLog.RpcLogCategory.Value('User')

        log = dict(
            level=log_level,
            message=formatted_msg,
            category=record.name,
            log_category=log_category
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
    def request_id(self) -> str:
        return self._request_id

    @property
    def worker_id(self) -> str:
        return self._worker_id

    # noinspection PyBroadException
    @staticmethod
    def _serialize_exception(exc: Exception):
        try:
            message = f'{type(exc).__name__}: {exc}'
        except Exception:
            message = ('Unhandled exception in function. '
                       'Could not serialize original exception message.')

        try:
            stack_trace = marshall_exception_trace(exc)
        except Exception:
            stack_trace = ''

        return protos.RpcException(message=message, stack_trace=stack_trace)

    async def _dispatch_grpc_request(self, request):
        content_type = request.WhichOneof('content')
        request_handler = getattr(self, f'_handle__{content_type}', None)
        if request_handler is None:
            # Don't crash on unknown messages.  Some of them can be ignored;
            # and if something goes really wrong the host can always just
            # kill the worker's process.
            logger.error(f'unknown StreamingMessage content type '
                         f'{content_type}')
            return

        resp = await request_handler(request)
        self._grpc_resp_queue.put_nowait(resp)

    async def _handle__worker_init_request(self, req):
        logger.info('Received WorkerInitRequest, request ID %s',
                    self.request_id)

        capabilities = {
            constants.RAW_HTTP_BODY_BYTES: _TRUE,
            constants.TYPED_DATA_COLLECTION: _TRUE,
            constants.RPC_HTTP_BODY_ONLY: _TRUE,
            constants.RPC_HTTP_TRIGGER_METADATA_REMOVED: _TRUE,
        }

        return protos.StreamingMessage(
            request_id=self.request_id,
            worker_init_response=protos.WorkerInitResponse(
                capabilities=capabilities,
                result=protos.StatusResult(
                    status=protos.StatusResult.Success)))

    async def _handle__function_load_request(self, req):
        func_request = req.function_load_request
        function_id = func_request.function_id

        logger.info(f'Received FunctionLoadRequest, '
                    f'request ID: {self.request_id}, '
                    f'function ID: {function_id}')
        try:
            func = loader.load_function(
                func_request.metadata.name,
                func_request.metadata.directory,
                func_request.metadata.script_file,
                func_request.metadata.entry_point)

            self._functions.add_function(
                function_id, func, func_request.metadata)

            logger.info('Successfully processed FunctionLoadRequest, '
                        f'request ID: {self.request_id}, '
                        f'function ID: {function_id}')

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
        trace_context = bindings.TraceContext(
            invoc_request.trace_context.trace_parent,
            invoc_request.trace_context.trace_state,
            invoc_request.trace_context.attributes)
        # Set the current `invocation_id` to the current task so
        # that our logging handler can find it.
        current_task = _CURRENT_TASK(self._loop)
        assert isinstance(current_task, ContextEnabledTask)
        current_task.set_azure_invocation_id(invocation_id)

        try:
            fi: functions.FunctionInfo = self._functions.get_function(
                function_id)

            function_invocation_logs: List[str] = [
                'Received FunctionInvocationRequest',
                f'request ID: {self.request_id}',
                f'function ID: {function_id}',
                f'invocation ID: {invocation_id}',
                f'function type: {"async" if fi.is_async else "sync"}'
            ]
            if not fi.is_async:
                function_invocation_logs.append(
                    f'sync threadpool max workers: {self._sync_tp_max_workers}'
                )
            logger.info(', '.join(function_invocation_logs))

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
                    fi.name, fi.directory, invocation_id, trace_context)

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
                raise RuntimeError(f'function {fi.name!r} without a $return '
                                   'binding returned a non-None value')

            output_data = []
            if fi.output_types:
                for out_name, out_type_info in fi.output_types.items():
                    val = args[out_name].get()
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
                            name=out_name,
                            data=rpc_val))

            return_value = None
            if fi.return_type is not None:
                return_value = bindings.to_outgoing_proto(
                    fi.return_type.binding_name, call_result,
                    pytype=fi.return_type.pytype)

            # Actively flush customer print() function to console
            sys.stdout.flush()

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

    async def _handle__function_environment_reload_request(self, req):
        """Only runs on Linux Consumption placeholder specialization.
        """
        try:
            logger.info('Received FunctionEnvironmentReloadRequest, '
                        'request ID: %s', self.request_id)

            func_env_reload_request = req.function_environment_reload_request

            # Import before clearing path cache so that the default
            # azure.functions modules is available in sys.modules for
            # customer use
            import azure.functions # NoQA

            # Append function project root to module finding sys.path
            if func_env_reload_request.function_app_directory:
                sys.path.append(func_env_reload_request.function_app_directory)

            # Clear sys.path import cache, reload all module from new sys.path
            sys.path_importer_cache.clear()

            # Reload environment variables
            os.environ.clear()
            env_vars = func_env_reload_request.environment_variables
            for var in env_vars:
                os.environ[var] = env_vars[var]

            # Apply PYTHON_THREADPOOL_THREAD_COUNT
            self._stop_sync_call_tp()
            self._sync_tp_max_workers = self._get_sync_tp_max_workers()
            self._sync_call_tp = (
                self._create_sync_call_tp(self._sync_tp_max_workers)
            )

            # Reload package namespaces for customer's libraries
            packages_to_reload = ['azure', 'google']
            for p in packages_to_reload:
                try:
                    logger.info(f'Reloading {p} module')
                    importlib.reload(sys.modules[p])
                except Exception as ex:
                    logger.info('Unable to reload {}: \n{}'.format(p, ex))
                logger.info(f'Reloaded {p} module')

            # Reload azure.functions to give user package precedence
            logger.info('Reloading azure.functions module at %s',
                        inspect.getfile(sys.modules['azure.functions']))
            try:
                importlib.reload(sys.modules['azure.functions'])
                logger.info('Reloaded azure.functions module now at %s',
                            inspect.getfile(sys.modules['azure.functions']))
            except Exception as ex:
                logger.info('Unable to reload azure.functions. '
                            'Using default. Exception:\n{}'.format(ex))

            # Change function app directory
            if getattr(func_env_reload_request,
                       'function_app_directory', None):
                self._change_cwd(
                    func_env_reload_request.function_app_directory)

            success_response = protos.FunctionEnvironmentReloadResponse(
                result=protos.StatusResult(
                    status=protos.StatusResult.Success))

            return protos.StreamingMessage(
                request_id=self.request_id,
                function_environment_reload_response=success_response)

        except Exception as ex:
            failure_response = protos.FunctionEnvironmentReloadResponse(
                result=protos.StatusResult(
                    status=protos.StatusResult.Failure,
                    exception=self._serialize_exception(ex)))

            return protos.StreamingMessage(
                request_id=self.request_id,
                function_environment_reload_response=failure_response)

    @disable_feature_by(constants.PYTHON_ROLLBACK_CWD_PATH)
    def _change_cwd(self, new_cwd: str):
        if os.path.exists(new_cwd):
            os.chdir(new_cwd)
            logger.info('Changing current working directory to %s', new_cwd)
        else:
            logger.warning('Directory %s is not found when reloading', new_cwd)

    def _stop_sync_call_tp(self):
        """Deallocate the current synchronous thread pool and assign
        self._sync_call_tp to None. If the thread pool does not exist,
        this will be a no op.
        """
        if getattr(self, '_sync_call_tp', None):
            self._sync_call_tp.shutdown()
            self._sync_call_tp = None

    def _get_sync_tp_max_workers(self) -> int:
        def tp_max_workers_validator(value: str) -> bool:
            try:
                int_value = int(value)
            except ValueError:
                logger.warning(f'{PYTHON_THREADPOOL_THREAD_COUNT} must be an '
                               'integer')
                return False

            if int_value < PYTHON_THREADPOOL_THREAD_COUNT_MIN or (
               int_value > PYTHON_THREADPOOL_THREAD_COUNT_MAX):
                logger.warning(f'{PYTHON_THREADPOOL_THREAD_COUNT} must be set '
                               'to a value between 1 and 32')
                return False

            return True

        return int(get_app_setting(
            setting=PYTHON_THREADPOOL_THREAD_COUNT,
            default_value=f'{PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT}',
            validator=tp_max_workers_validator))

    def _create_sync_call_tp(
            self, max_worker: int) -> concurrent.futures.Executor:
        """Create a thread pool executor with max_worker. This is a wrapper
        over ThreadPoolExecutor constructor. Consider calling this method after
        _stop_sync_call_tp() to ensure only 1 synchronous thread pool is
        running.
        """
        return concurrent.futures.ThreadPoolExecutor(
            max_workers=max_worker
        )

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
            error_logger.exception('unhandled error in gRPC thread')
            raise


class AsyncLoggingHandler(logging.Handler):

    def emit(self, record: LogRecord) -> None:
        # Since we disable console log after gRPC channel is initiated,
        # we should redirect all the messages into dispatcher.

        # When dispatcher receives an exception, it should switch back
        # to console logging. However, it is possible that
        # __current_dispatcher__ is set to None as there are still messages
        # buffered in this handler, not calling the emit yet.
        msg = self.format(record)
        try:
            Dispatcher.current.on_logging(record, msg)
        except RuntimeError as runtime_error:
            # This will cause 'Dispatcher not found' failure.
            # Logging such of an issue will cause infinite loop of gRPC logging
            # To mitigate, we should suppress the 2nd level error logging here
            # and use print function to report exception instead.
            print(f'{CONSOLE_LOG_PREFIX} ERROR: {str(runtime_error)}',
                  file=sys.stderr, flush=True)


class ContextEnabledTask(asyncio.Task):

    AZURE_INVOCATION_ID = '__azure_function_invocation_id__'

    def __init__(self, coro, loop):
        super().__init__(coro, loop=loop)

        current_task = _CURRENT_TASK(loop)
        if current_task is not None:
            invocation_id = getattr(
                current_task, self.AZURE_INVOCATION_ID, None)
            if invocation_id is not None:
                self.set_azure_invocation_id(invocation_id)

    def set_azure_invocation_id(self, invocation_id: str) -> None:
        setattr(self, self.AZURE_INVOCATION_ID, invocation_id)


def get_current_invocation_id() -> Optional[str]:
    loop = asyncio._get_running_loop()
    if loop is not None:
        current_task = _CURRENT_TASK(loop)
        if current_task is not None:
            task_invocation_id = getattr(current_task,
                                         ContextEnabledTask.AZURE_INVOCATION_ID,
                                         None)
            if task_invocation_id is not None:
                return task_invocation_id

    return getattr(_invocation_id_local, 'v', None)


_invocation_id_local = threading.local()
