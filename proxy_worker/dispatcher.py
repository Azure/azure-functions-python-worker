# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import concurrent.futures
import logging
import os
import queue
import sys
import threading
import traceback
import typing
from asyncio import AbstractEventLoop
from dataclasses import dataclass
from typing import Any, Optional

import grpc
from proxy_worker import protos
from proxy_worker.logging import (
    CONSOLE_LOG_PREFIX,
    disable_console_logging,
    enable_console_logging,
    error_logger,
    is_system_log_category,
    logger,
)
from proxy_worker.utils.common import (
    get_app_setting,
    get_script_file_name,
    is_envvar_true,
)
from proxy_worker.utils.constants import (
    PYTHON_ENABLE_DEBUG_LOGGING,
    PYTHON_THREADPOOL_THREAD_COUNT,
)
from proxy_worker.version import VERSION

from .utils.dependency import DependencyManager

# Library worker import reloaded in init and reload request
_library_worker = None


class ContextEnabledTask(asyncio.Task):
    AZURE_INVOCATION_ID = '__azure_function_invocation_id__'

    def __init__(self, coro, loop, context=None, **kwargs):
        super().__init__(coro, loop=loop, context=context, **kwargs)

        current_task = asyncio.current_task(loop)
        if current_task is not None:
            invocation_id = getattr(
                current_task, self.AZURE_INVOCATION_ID, None)
            if invocation_id is not None:
                self.set_azure_invocation_id(invocation_id)

    def set_azure_invocation_id(self, invocation_id: str) -> None:
        setattr(self, self.AZURE_INVOCATION_ID, invocation_id)


_invocation_id_local = threading.local()


def get_current_invocation_id() -> Optional[Any]:
    loop = asyncio._get_running_loop()
    if loop is not None:
        current_task = asyncio.current_task(loop)
        if current_task is not None:
            task_invocation_id = getattr(current_task,
                                         ContextEnabledTask.AZURE_INVOCATION_ID,
                                         None)
            if task_invocation_id is not None:
                return task_invocation_id

    return getattr(_invocation_id_local, 'invocation_id', None)


class AsyncLoggingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
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


@dataclass
class WorkerRequest:
    name: str
    request: str
    properties: Optional[dict[str, typing.Any]] = None


class DispatcherMeta(type):
    __current_dispatcher__: Optional["Dispatcher"] = None

    @property
    def current(cls):
        disp = cls.__current_dispatcher__
        if disp is None:
            raise RuntimeError('no currently running Dispatcher is found')
        return disp


class Dispatcher(metaclass=DispatcherMeta):
    _GRPC_STOP_RESPONSE = object()

    def __init__(self, loop: AbstractEventLoop, host: str, port: int,
                 worker_id: str, request_id: str,
                 grpc_connect_timeout: float,
                 grpc_max_msg_len: int = -1) -> None:
        self._loop = loop
        self._host = host
        self._port = port
        self._request_id = request_id
        self._worker_id = worker_id
        self._grpc_connect_timeout: float = grpc_connect_timeout
        self._grpc_max_msg_len: int = grpc_max_msg_len
        self._old_task_factory: Optional[Any] = None

        self._grpc_resp_queue: queue.Queue = queue.Queue()
        self._grpc_connected_fut = loop.create_future()
        self._grpc_thread: Optional[threading.Thread] = threading.Thread(
            name='grpc_local-thread', target=self.__poll_grpc)

        self._sync_call_tp: Optional[concurrent.futures.Executor] = (
            self._create_sync_call_tp(self._get_sync_tp_max_workers()))

    def on_logging(self, record: logging.LogRecord,
                   formatted_msg: str) -> None:
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

    @classmethod
    async def connect(cls, host: str, port: int, worker_id: str,
                      request_id: str, connect_timeout: float):
        loop = asyncio.events.get_event_loop()
        disp = cls(loop, host, port, worker_id, request_id, connect_timeout)
        # Safety check for mypy
        if disp._grpc_thread is not None:
            disp._grpc_thread.start()
        await disp._grpc_connected_fut
        logger.info('Successfully opened gRPC channel to %s:%s ', host, port)
        return disp

    def __poll_grpc(self):
        options = []
        if self._grpc_max_msg_len:
            options.append(('grpc_local.max_receive_message_length',
                            self._grpc_max_msg_len))
            options.append(('grpc_local.max_send_message_length',
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
            error_logger.exception(
                'unhandled error in gRPC thread. Exception: {0}'.format(
                    ''.join(traceback.format_exception(ex))))
            raise

    async def _dispatch_grpc_request(self, request):
        content_type = request.WhichOneof("content")

        match content_type:
            case "worker_init_request":
                request_handler = self._handle__worker_init_request
            case "function_environment_reload_request":
                request_handler = self._handle__function_environment_reload_request
            case "functions_metadata_request":
                request_handler = self._handle__functions_metadata_request
            case "function_load_request":
                request_handler = self._handle__function_load_request
            case "worker_status_request":
                request_handler = self._handle__worker_status_request
            case "invocation_request":
                request_handler = self._handle__invocation_request
            case _:
                # Don't crash on unknown messages. Log the error and return.
                logger.error("Unknown StreamingMessage content type: %s", content_type)
                return

        resp = await request_handler(request)
        self._grpc_resp_queue.put_nowait(resp)

    async def dispatch_forever(self):  # sourcery skip: swap-if-expression
        if DispatcherMeta.__current_dispatcher__ is not None:
            raise RuntimeError('there can be only one running dispatcher per '
                               'process')

        self._old_task_factory = self._loop.get_task_factory()

        DispatcherMeta.__current_dispatcher__ = self
        try:
            forever = self._loop.create_future()

            self._grpc_resp_queue.put_nowait(
                protos.StreamingMessage(
                    request_id=self.request_id,
                    start_stream=protos.StartStream(
                        worker_id=self.worker_id)))

            # In Python 3.11+, constructing a task has an optional context
            # parameter. Allow for this param to be passed to ContextEnabledTask
            self._loop.set_task_factory(
                lambda loop, coro, context=None, **kwargs: ContextEnabledTask(
                    coro, loop=loop, context=context, **kwargs))

            # Detach console logging before enabling GRPC channel logging
            logger.info('Detaching console logging.')
            disable_console_logging()

            # Attach gRPC logging to the root logger. Since gRPC channel is
            # established, should use it for system and user logs
            logging_handler = AsyncLoggingHandler()
            root_logger = logging.getLogger()

            log_level = logging.INFO if not is_envvar_true(
                PYTHON_ENABLE_DEBUG_LOGGING) else logging.DEBUG

            root_logger.setLevel(log_level)
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

            self._loop.set_task_factory(self._old_task_factory)
            self.stop()

    def stop(self) -> None:
        if self._grpc_thread is not None:
            self._grpc_resp_queue.put_nowait(self._GRPC_STOP_RESPONSE)
            self._grpc_thread.join()
            self._grpc_thread = None

        self._stop_sync_call_tp()

    def _stop_sync_call_tp(self):
        """Deallocate the current synchronous thread pool and assign
        self._sync_call_tp to None. If the thread pool does not exist,
        this will be a no op.
        """
        if getattr(self, '_sync_call_tp', None):
            assert self._sync_call_tp is not None  # mypy fix
            self._sync_call_tp.shutdown()
            self._sync_call_tp = None

    @staticmethod
    def _create_sync_call_tp(max_worker: Optional[int]) -> concurrent.futures.Executor:
        """Create a thread pool executor with max_worker. This is a wrapper
        over ThreadPoolExecutor constructor. Consider calling this method after
        _stop_sync_call_tp() to ensure only 1 synchronous thread pool is
        running.
        """
        return concurrent.futures.ThreadPoolExecutor(
            max_workers=max_worker
        )

    @staticmethod
    def _get_sync_tp_max_workers() -> typing.Optional[int]:
        def tp_max_workers_validator(value: str) -> bool:
            try:
                int_value = int(value)
            except ValueError:
                logger.warning('%s must be an integer',
                               PYTHON_THREADPOOL_THREAD_COUNT)
                return False

            if int_value < 1:
                logger.warning(
                    '%s must be set to a value between 1 and sys.maxint. '
                    'Reverting to default value for max_workers',
                    PYTHON_THREADPOOL_THREAD_COUNT,
                    1)
                return False
            return True

        max_workers = get_app_setting(setting=PYTHON_THREADPOOL_THREAD_COUNT,
                                      validator=tp_max_workers_validator)

        # We can box the app setting as int for earlier python versions.
        return int(max_workers) if max_workers else None

    @staticmethod
    def reload_library_worker(directory: str):
        global _library_worker
        v2_scriptfile = os.path.join(directory, get_script_file_name())
        if os.path.exists(v2_scriptfile):
            try:
                import azure_functions_worker_v2  # NoQA
                _library_worker = azure_functions_worker_v2
                logger.debug("azure_functions_worker_v2 import succeeded: %s",
                             _library_worker.__file__)
            except ImportError:
                logger.debug("azure_functions_worker_v2 library not found: : %s",
                             traceback.format_exc())
        else:
            try:
                import azure_functions_worker_v1  # NoQA
                _library_worker = azure_functions_worker_v1
                logger.debug("azure_functions_worker_v1 import succeeded: %s",
                             _library_worker.__file__)  # type: ignore[union-attr]
            except ImportError:
                logger.debug("azure_functions_worker_v1 library not found: %s",
                             traceback.format_exc())

    async def _handle__worker_init_request(self, request):
        logger.info('Received WorkerInitRequest, '
                    'python version %s, '
                    'worker version %s, '
                    'request ID %s. '
                    'To enable debug level logging, please refer to '
                    'https://aka.ms/python-enable-debug-logging',
                    sys.version,
                    VERSION,
                    self.request_id)

        if DependencyManager.is_in_linux_consumption():
            import azure_functions_worker_v2

        if DependencyManager.should_load_cx_dependencies():
            DependencyManager.prioritize_customer_dependencies()

        directory = request.worker_init_request.function_app_directory
        self.reload_library_worker(directory)

        init_request = WorkerRequest(name="WorkerInitRequest",
                                     request=request,
                                     properties={"protos": protos,
                                                 "host": self._host})
        init_response = await (
            _library_worker.worker_init_request(  # type: ignore[union-attr]
                init_request))

        return protos.StreamingMessage(
            request_id=self.request_id,
            worker_init_response=init_response)

    async def _handle__function_environment_reload_request(self, request):
        logger.info('Received FunctionEnvironmentReloadRequest, '
                    'request ID: %s, '
                    'To enable debug level logging, please refer to '
                    'https://aka.ms/python-enable-debug-logging',
                    self.request_id)

        func_env_reload_request = \
            request.function_environment_reload_request
        directory = func_env_reload_request.function_app_directory

        DependencyManager.prioritize_customer_dependencies(directory)
        self.reload_library_worker(directory)

        env_reload_request = WorkerRequest(name="FunctionEnvironmentReloadRequest",
                                           request=request,
                                           properties={"protos": protos,
                                                       "host": self._host})
        env_reload_response = await (
            _library_worker.function_environment_reload_request(  # type: ignore[union-attr]  # noqa
                env_reload_request))

        return protos.StreamingMessage(
            request_id=self.request_id,
            function_environment_reload_response=env_reload_response)

    async def _handle__worker_status_request(self, request):
        # Logging is not necessary in this request since the response is used
        # for host to judge scale decisions of out-of-proc languages.
        # Having log here will reduce the responsiveness of the worker.
        return protos.StreamingMessage(
            request_id=request.request_id,
            worker_status_response=protos.WorkerStatusResponse())

    async def _handle__functions_metadata_request(self, request):
        logger.info(
            'Received WorkerMetadataRequest, request ID %s, '
            'worker id: %s',
            self.request_id, self.worker_id)

        metadata_request = WorkerRequest(name="WorkerMetadataRequest", request=request)
        metadata_response = await (
            _library_worker.functions_metadata_request(  # type: ignore[union-attr]
                metadata_request))

        return protos.StreamingMessage(
            request_id=request.request_id,
            function_metadata_response=metadata_response)

    async def _handle__function_load_request(self, request):
        func_request = request.function_load_request
        function_id = func_request.function_id
        function_metadata = func_request.metadata
        function_name = function_metadata.name

        logger.info(
            'Received WorkerLoadRequest, request ID %s, function_id: %s,'
            'function_name: %s, worker_id: %s',
            self.request_id, function_id, function_name, self.worker_id)

        load_request = WorkerRequest(name="FunctionLoadRequest ", request=request)
        load_response = await (
            _library_worker.function_load_request(  # type: ignore[union-attr]
                load_request))

        return protos.StreamingMessage(
            request_id=self.request_id,
            function_load_response=load_response)

    async def _handle__invocation_request(self, request):
        invoc_request = request.invocation_request
        invocation_id = invoc_request.invocation_id
        function_id = invoc_request.function_id

        logger.info(
            'Received FunctionInvocationRequest, request ID %s, function_id: %s,'
            'invocation_id: %s, worker_id: %s',
            self.request_id, function_id, invocation_id, self.worker_id)

        invocation_request = WorkerRequest(name="FunctionInvocationRequest",
                                           request=request,
                                           properties={
                                               "threadpool": self._sync_call_tp})
        invocation_response = await (
            _library_worker.invocation_request(  # type: ignore[union-attr]
                invocation_request))

        return protos.StreamingMessage(
            request_id=self.request_id,
            invocation_response=invocation_response)
