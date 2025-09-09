# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
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
    get_script_file_name,
    is_envvar_true,
    check_python_eol
)
from proxy_worker.utils.constants import (
    PYTHON_ENABLE_DEBUG_LOGGING,
)
from proxy_worker.version import VERSION

from .utils.dependency import DependencyManager

# Library worker import reloaded in init and reload request
_library_worker = None

# Thread-local invocation ID registry for efficient lookup
_thread_invocation_registry: typing.Dict[int, str] = {}
_registry_lock = threading.Lock()

# Global current invocation tracker (as a fallback)
_current_invocation_id: Optional[str] = None
_current_invocation_lock = threading.Lock()


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


def set_thread_invocation_id(thread_id: int, invocation_id: str) -> None:
    """Set the invocation ID for a specific thread"""
    with _registry_lock:
        _thread_invocation_registry[thread_id] = invocation_id


def clear_thread_invocation_id(thread_id: int) -> None:
    """Clear the invocation ID for a specific thread"""
    with _registry_lock:
        _thread_invocation_registry.pop(thread_id, None)


def get_thread_invocation_id(thread_id: int) -> Optional[str]:
    """Get the invocation ID for a specific thread"""
    with _registry_lock:
        return _thread_invocation_registry.get(thread_id)


def set_current_invocation_id(invocation_id: str) -> None:
    """Set the global current invocation ID"""
    global _current_invocation_id
    with _current_invocation_lock:
        _current_invocation_id = invocation_id


def get_global_current_invocation_id() -> Optional[str]:
    """Get the global current invocation ID"""
    with _current_invocation_lock:
        return _current_invocation_id


def get_current_invocation_id() -> Optional[Any]:
    # Check global current invocation first (most up-to-date)
    global_invocation_id = get_global_current_invocation_id()
    if global_invocation_id is not None:
        return global_invocation_id

    # Check asyncio task context
    try:
        loop = asyncio._get_running_loop()
        if loop is not None:
            current_task = asyncio.current_task(loop)
            if current_task is not None:
                task_invocation_id = getattr(current_task,
                                             ContextEnabledTask.AZURE_INVOCATION_ID,
                                             None)
                if task_invocation_id is not None:
                    return task_invocation_id
    except RuntimeError:
        # No event loop running
        pass

    # Check the thread-local invocation ID registry
    current_thread_id = threading.get_ident()
    thread_invocation_id = get_thread_invocation_id(current_thread_id)
    if thread_invocation_id is not None:
        return thread_invocation_id

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

        match content_type:  # noqa
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

        # Ask the library runtime to stop its threadpool (if loaded)
        global _library_worker
        if _library_worker is not None:
            stop_exec = getattr(_library_worker, 'stop_threadpool_executor', None)
            if callable(stop_exec):
                try:
                    stop_exec()
                except Exception:  # pragma: no cover - best effort
                    logger.debug('Exception while stopping threadpool executor',
                                 exc_info=True)

    # Removed: threadpool lifecycle now handled in runtime libraries

    @staticmethod
    def reload_library_worker(directory: str):
        global _library_worker
        v2_scriptfile = os.path.join(directory, get_script_file_name())
        if os.path.exists(v2_scriptfile):
            try:
                import azure_functions_runtime  # NoQA
                _library_worker = azure_functions_runtime
                logger.debug("azure_functions_runtime import succeeded: %s",
                             _library_worker.__file__)
            except ImportError:
                logger.debug("azure_functions_runtime library not found: : %s",
                             traceback.format_exc())
        else:
            try:
                import azure_functions_runtime_v1  # NoQA
                _library_worker = azure_functions_runtime_v1
                logger.debug("azure_functions_runtime_v1 import succeeded: %s",
                             _library_worker.__file__)  # type: ignore[union-attr]
            except ImportError:
                logger.debug("azure_functions_runtime_v1 library not found: %s",
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
        check_python_eol()

        if DependencyManager.is_in_linux_consumption():
            import azure_functions_runtime  # NoQA

        if DependencyManager.should_load_cx_dependencies():
            DependencyManager.prioritize_customer_dependencies()

        directory = request.worker_init_request.function_app_directory
        self.reload_library_worker(directory)
        logger.info('Using library: %s, '
                    'library version: %s',
                    _library_worker,
                    _library_worker.version.VERSION)

        init_request = WorkerRequest(
            name="WorkerInitRequest",
            request=request,
            properties={"protos": protos, "host": self._host},
        )

        try:
            _library_worker.start_threadpool_executor()
        except AttributeError:
            logger.debug(
                "Threadpool executor APIs not present in runtime; "
                "skipping start."
            )
        init_response = await (
            _library_worker.worker_init_request(
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
        check_python_eol()

        func_env_reload_request = \
            request.function_environment_reload_request
        directory = func_env_reload_request.function_app_directory

        DependencyManager.prioritize_customer_dependencies(directory)
        self.reload_library_worker(directory)
        logger.info('Using library: %s, '
                    'library version: %s',
                    _library_worker,
                    _library_worker.version.VERSION)

        env_reload_request = WorkerRequest(
            name="FunctionEnvironmentReloadRequest",
            request=request,
            properties={"protos": protos, "host": self._host},
        )

        try:
            _library_worker.start_threadpool_executor()
        except AttributeError:
            logger.debug(
                "Threadpool executor APIs not present in runtime during "
                "env reload; skipping."
            )
        env_reload_response = await (
            _library_worker.function_environment_reload_request(
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
            'Received WorkerLoadRequest, request ID %s, function_id: %s, '
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
            'Received FunctionInvocationRequest, request ID %s, function_id: %s, '
            'invocation_id: %s, worker_id: %s',
            self.request_id, function_id, invocation_id, self.worker_id)

        # Set the global current invocation ID first (for all threads to access)
        set_current_invocation_id(invocation_id)

        # Set the current `invocation_id` to the current task so
        # that our logging handler can find it.
        current_task = asyncio.current_task()
        if current_task is not None and isinstance(current_task, ContextEnabledTask):
            current_task.set_azure_invocation_id(invocation_id)

        # Register the invocation ID for the current thread
        current_thread_id = threading.get_ident()
        set_thread_invocation_id(current_thread_id, invocation_id)

        try:
            invocation_request = WorkerRequest(name="FunctionInvocationRequest",
                                               request=request)
            invocation_response = await (
                _library_worker.invocation_request(  # type: ignore[union-attr]
                    invocation_request))

            return protos.StreamingMessage(
                request_id=self.request_id,
                invocation_response=invocation_response)
        except Exception:
            # Clear thread registry on exception to prevent stale IDs
            clear_thread_invocation_id(current_thread_id)
            raise
