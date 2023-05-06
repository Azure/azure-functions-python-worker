# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""GRPC client.

Implements loading and execution of Python workers.
"""

import asyncio
import concurrent.futures
import logging
import os
import platform
import queue
import sys
import threading
from asyncio import BaseEventLoop
from logging import LogRecord
from typing import List, Optional

import grpc

from . import bindings, constants, functions, loader, protos
from .bindings.shared_memory_data_transfer import SharedMemoryManager
from .constants import (PYTHON_THREADPOOL_THREAD_COUNT,
                        PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT,
                        PYTHON_THREADPOOL_THREAD_COUNT_MAX_37,
                        PYTHON_THREADPOOL_THREAD_COUNT_MIN,
                        PYTHON_ENABLE_DEBUG_LOGGING, SCRIPT_FILE_NAME,
                        PYTHON_LANGUAGE_RUNTIME, PYTHON_LOAD_FUNCTIONS_INIT)
from .extension import ExtensionManager
from .logging import disable_console_logging, enable_console_logging
from .logging import enable_debug_logging_recommendation
from .logging import (logger, error_logger, is_system_log_category,
                      CONSOLE_LOG_PREFIX, format_exception)
from .utils.common import get_app_setting, is_envvar_true
from .utils.dependency import DependencyManager
from .utils.tracing import marshall_exception_trace
from .utils.wrappers import disable_feature_by
from .version import VERSION

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
        self._function_data_cache_enabled = False
        self._functions = functions.Registry()
        self._shmem_mgr = SharedMemoryManager()

        self._old_task_factory = None

        # We allow the customer to change synchronous thread pool max worker
        # count by setting the PYTHON_THREADPOOL_THREAD_COUNT app setting.
        #   For 3.[6|7|8] The default value is 1.
        #   For 3.9, we don't set this value by default but we honor incoming
        #     the app setting.
        self._sync_call_tp: concurrent.futures.Executor = (
            self._create_sync_call_tp(self._get_sync_tp_max_workers())
        )

        self._grpc_connect_timeout: float = grpc_connect_timeout
        # This is set to -1 by default to remove the limitation on msg size
        self._grpc_max_msg_len: int = grpc_max_msg_len
        self._grpc_resp_queue: queue.Queue = queue.Queue()
        self._grpc_connected_fut = loop.create_future()
        self._grpc_thread: threading.Thread = threading.Thread(
            name='grpc-thread', target=self.__poll_grpc)

    @staticmethod
    def get_worker_metadata():
        return protos.WorkerMetadata(
            runtime_name=PYTHON_LANGUAGE_RUNTIME,
            runtime_version=f"{sys.version_info.major}."
                            f"{sys.version_info.minor}",
            worker_version=VERSION,
            worker_bitness=platform.machine(),
            custom_properties={})

    def get_sync_tp_workers_set(self):
        """We don't know the exact value of the threadcount set for the Python
         3.9 scenarios (as we'll start passing only None by default), and we
         need to get that information.

         Ref: concurrent.futures.thread.ThreadPoolExecutor.__init__._max_workers
        """
        return self._sync_call_tp._max_workers

    @classmethod
    async def connect(cls, host: str, port: int, worker_id: str,
                      request_id: str, connect_timeout: float):
        loop = asyncio.events.get_event_loop()
        disp = cls(loop, host, port, worker_id, request_id, connect_timeout)
        disp._grpc_thread.start()
        await disp._grpc_connected_fut
        logger.info('Successfully opened gRPC channel to %s:%s ', host, port)
        return disp

    async def dispatch_forever(self):  # sourcery skip: swap-if-expression
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
            logger.error('unknown StreamingMessage content type %s',
                         content_type)
            return

        resp = await request_handler(request)
        self._grpc_resp_queue.put_nowait(resp)

    async def _handle__worker_init_request(self, request):
        logger.info('Received WorkerInitRequest, '
                    'python version %s, worker version %s, request ID %s',
                    sys.version, VERSION, self.request_id)
        enable_debug_logging_recommendation()

        worker_init_request = request.worker_init_request
        host_capabilities = worker_init_request.capabilities
        if constants.FUNCTION_DATA_CACHE in host_capabilities:
            val = host_capabilities[constants.FUNCTION_DATA_CACHE]
            self._function_data_cache_enabled = val == _TRUE

        capabilities = {
            constants.RAW_HTTP_BODY_BYTES: _TRUE,
            constants.TYPED_DATA_COLLECTION: _TRUE,
            constants.RPC_HTTP_BODY_ONLY: _TRUE,
            constants.WORKER_STATUS: _TRUE,
            constants.RPC_HTTP_TRIGGER_METADATA_REMOVED: _TRUE,
            constants.SHARED_MEMORY_DATA_TRANSFER: _TRUE,
        }

        # Can detech worker packages only when customer's code is present
        # This only works in dedicated and premium sku.
        # The consumption sku will switch on environment_reload request.
        if not DependencyManager.is_in_linux_consumption():
            DependencyManager.prioritize_customer_dependencies()

        if DependencyManager.is_in_linux_consumption() \
                and is_envvar_true(PYTHON_LOAD_FUNCTIONS_INIT):
            logger.info(
                "PYTHON_LOAD_FUNCTIONS_INIT enabled. Importing azure functions")
            import azure.functions  # NoQA

        # loading bindings registry and saving results to a static
        # dictionary which will be later used in the invocation request
        bindings.load_binding_registry()

        return protos.StreamingMessage(
            request_id=self.request_id,
            worker_init_response=protos.WorkerInitResponse(
                capabilities=capabilities,
                worker_metadata=self.get_worker_metadata(),
                result=protos.StatusResult(
                    status=protos.StatusResult.Success)))

    async def _handle__worker_status_request(self, request):
        # Logging is not necessary in this request since the response is used
        # for host to judge scale decisions of out-of-proc languages.
        # Having log here will reduce the responsiveness of the worker.
        return protos.StreamingMessage(
            request_id=request.request_id,
            worker_status_response=protos.WorkerStatusResponse())

    async def _handle__functions_metadata_request(self, request):
        metadata_request = request.functions_metadata_request
        directory = metadata_request.function_app_directory
        function_path = os.path.join(directory, SCRIPT_FILE_NAME)

        logger.info(
            'Received WorkerMetadataRequest, request ID %s, directory: %s',
            self.request_id, directory)

        if not os.path.exists(function_path):
            # Fallback to legacy model
            logger.info("%s does not exist. "
                        "Switching to host indexing.", SCRIPT_FILE_NAME)
            return protos.StreamingMessage(
                request_id=request.request_id,
                function_metadata_response=protos.FunctionMetadataResponse(
                    use_default_metadata_indexing=True,
                    result=protos.StatusResult(
                        status=protos.StatusResult.Success)))

        try:
            fx_metadata_results = self.index_functions(function_path)

            return protos.StreamingMessage(
                request_id=request.request_id,
                function_metadata_response=protos.FunctionMetadataResponse(
                    function_metadata_results=fx_metadata_results,
                    result=protos.StatusResult(
                        status=protos.StatusResult.Success)))

        except Exception as ex:
            return protos.StreamingMessage(
                request_id=self.request_id,
                function_metadata_response=protos.FunctionMetadataResponse(
                    result=protos.StatusResult(
                        status=protos.StatusResult.Failure,
                        exception=self._serialize_exception(ex))))

    async def _handle__function_load_request(self, request):
        func_request = request.function_load_request
        function_id = func_request.function_id
        function_metadata = func_request.metadata
        function_name = function_metadata.name
        function_path = os.path.join(function_metadata.directory,
                                     SCRIPT_FILE_NAME)

        logger.info(
            'Received WorkerLoadRequest, request ID %s, function_id: %s,'
            'function_name: %s,', self.request_id, function_id, function_name)

        try:
            if not self._functions.get_function(function_id):
                if function_metadata.properties.get("worker_indexed", False) \
                        or os.path.exists(function_path):
                    # This is for the second worker and above where the worker
                    # indexing is enabled and load request is called without
                    # calling the metadata request. In this case we index the
                    # function and update the workers registry
                    logger.info(f"Indexing function {function_name} in the "
                                f"load request")
                    _ = self.index_functions(function_path)
                else:
                    # legacy function
                    func = loader.load_function(
                        func_request.metadata.name,
                        func_request.metadata.directory,
                        func_request.metadata.script_file,
                        func_request.metadata.entry_point)

                    self._functions.add_function(
                        function_id, func, func_request.metadata)

                    ExtensionManager.function_load_extension(
                        function_name,
                        func_request.metadata.directory
                    )

                    logger.info('Successfully processed FunctionLoadRequest, '
                                'request ID: %s, '
                                'function ID: %s,'
                                'function Name: %s', self.request_id,
                                function_id,
                                function_name)

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

    async def _handle__invocation_request(self, request):
        invoc_request = request.invocation_request
        invocation_id = invoc_request.invocation_id
        function_id = invoc_request.function_id

        # Set the current `invocation_id` to the current task so
        # that our logging handler can find it.
        current_task = _CURRENT_TASK(self._loop)
        assert isinstance(current_task, ContextEnabledTask)
        current_task.set_azure_invocation_id(invocation_id)

        try:
            fi: functions.FunctionInfo = self._functions.get_function(
                function_id)
            assert fi is not None

            function_invocation_logs: List[str] = [
                'Received FunctionInvocationRequest',
                f'request ID: {self.request_id}',
                f'function ID: {function_id}',
                f'function name: {fi.name}',
                f'invocation ID: {invocation_id}',
                f'function type: {"async" if fi.is_async else "sync"}'
            ]
            if not fi.is_async:
                function_invocation_logs.append(
                    f'sync threadpool max workers: '
                    f'{self.get_sync_tp_workers_set()}'
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
                    pb_type_info.binding_name, pb,
                    trigger_metadata=trigger_metadata,
                    pytype=pb_type_info.pytype,
                    shmem_mgr=self._shmem_mgr)

            fi_context = self._get_context(invoc_request, fi.name, fi.directory)

            # Use local thread storage to store the invocation ID
            # for a customer's threads
            fi_context.thread_local_storage.invocation_id = invocation_id
            if fi.requires_context:
                args['context'] = fi_context

            if fi.output_types:
                for name in fi.output_types:
                    args[name] = bindings.Out()

            if fi.is_async:
                call_result = await self._run_async_func(
                    fi_context, fi.func, args
                )
            else:
                call_result = await self._loop.run_in_executor(
                    self._sync_call_tp,
                    self._run_sync_func,
                    invocation_id, fi_context, fi.func, args)
            if call_result is not None and not fi.has_return:
                raise RuntimeError(f'function {fi.name!r} without a $return '
                                   'binding returned a non-None value')

            output_data = []
            cache_enabled = self._function_data_cache_enabled
            if fi.output_types:
                for out_name, out_type_info in fi.output_types.items():
                    val = args[out_name].get()
                    if val is None:
                        # TODO: is the "Out" parameter optional?
                        # Can "None" be marshaled into protos.TypedData?
                        continue

                    param_binding = bindings.to_outgoing_param_binding(
                        out_type_info.binding_name, val,
                        pytype=out_type_info.pytype,
                        out_name=out_name, shmem_mgr=self._shmem_mgr,
                        is_function_data_cache_enabled=cache_enabled)
                    output_data.append(param_binding)

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

    async def _handle__function_environment_reload_request(self, request):
        """Only runs on Linux Consumption placeholder specialization.
        """
        try:
            logger.info('Received FunctionEnvironmentReloadRequest, '
                        'request ID: %s', self.request_id)
            enable_debug_logging_recommendation()

            func_env_reload_request = \
                request.function_environment_reload_request

            if not is_envvar_true(PYTHON_LOAD_FUNCTIONS_INIT):
                # Import before clearing path cache so that the default
                # azure.functions modules is available in sys.modules for
                # customer use
                import azure.functions  # NoQA

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
            self._sync_call_tp = (
                self._create_sync_call_tp(self._get_sync_tp_max_workers())
            )

            if is_envvar_true(PYTHON_ENABLE_DEBUG_LOGGING):
                root_logger = logging.getLogger()
                root_logger.setLevel(logging.DEBUG)

            # Reload azure google namespaces
            DependencyManager.reload_customer_libraries(
                func_env_reload_request.function_app_directory
            )

            # calling load_binding_registry again since the
            # reload_customer_libraries call clears the registry
            bindings.load_binding_registry()

            # Change function app directory
            if getattr(func_env_reload_request,
                       'function_app_directory', None):
                self._change_cwd(
                    func_env_reload_request.function_app_directory)

            success_response = protos.FunctionEnvironmentReloadResponse(
                capabilities={},
                worker_metadata=self.get_worker_metadata(),
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

    def index_functions(self, function_path: str):
        indexed_functions = loader.index_function_app(function_path)
        logger.info('Indexed function app and found %s functions',
                    len(indexed_functions))

        if indexed_functions:
            indexed_function_logs: List[str] = []
            for func in indexed_functions:
                function_log = "Function Name: {}, Function Binding: {}" \
                    .format(func.get_function_name(),
                            [(binding.type, binding.name) for binding in
                             func.get_bindings()])
                indexed_function_logs.append(function_log)

            logger.info(
                'Successfully processed FunctionMetadataRequest for '
                'functions: %s', " ".join(indexed_function_logs))

            fx_metadata_results = loader.process_indexed_function(
                self._functions,
                indexed_functions)

            return fx_metadata_results

    async def _handle__close_shared_memory_resources_request(self, request):
        """
        Frees any memory maps that were produced as output for a given
        invocation.
        This is called after the functions host is done reading the output from
        the worker and wants the worker to free up those resources.
        If the cache is enabled, let the host decide when to delete the
        resources. Just drop the reference from the worker.
        If the cache is not enabled, the worker should free the resources as at
        this point the host has read the memory maps and does not need them.
        """
        close_request = request.close_shared_memory_resources_request
        map_names = close_request.map_names
        # Assign default value of False to all result values.
        # If we are successfully able to close a memory map, its result will be
        # set to True.
        results = {mem_map_name: False for mem_map_name in map_names}

        try:
            for map_name in map_names:
                try:
                    to_delete_resources = not self._function_data_cache_enabled
                    success = self._shmem_mgr.free_mem_map(map_name,
                                                           to_delete_resources)
                    results[map_name] = success
                except Exception as e:
                    logger.error('Cannot free memory map %s - %s', map_name, e,
                                 exc_info=True)
        finally:
            response = protos.CloseSharedMemoryResourcesResponse(
                close_map_results=results)
            return protos.StreamingMessage(
                request_id=self.request_id,
                close_shared_memory_resources_response=response)

    @staticmethod
    def _get_context(invoc_request: protos.InvocationRequest, name: str,
                     directory: str) -> bindings.Context:
        """ For more information refer: https://aka.ms/azfunc-invocation-context
        """
        trace_context = bindings.TraceContext(
            invoc_request.trace_context.trace_parent,
            invoc_request.trace_context.trace_state,
            invoc_request.trace_context.attributes)

        retry_context = bindings.RetryContext(
            invoc_request.retry_context.retry_count,
            invoc_request.retry_context.max_retry_count,
            invoc_request.retry_context.exception)

        return bindings.Context(
            name, directory, invoc_request.invocation_id,
            _invocation_id_local, trace_context, retry_context)

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

    @staticmethod
    def _get_sync_tp_max_workers() -> Optional[int]:
        def tp_max_workers_validator(value: str) -> bool:
            try:
                int_value = int(value)
            except ValueError:
                logger.warning('%s must be an integer',
                               PYTHON_THREADPOOL_THREAD_COUNT)
                return False

            if int_value < PYTHON_THREADPOOL_THREAD_COUNT_MIN:
                logger.warning(
                    '%s must be set to a value between %s and sys.maxint. '
                    'Reverting to default value for max_workers',
                    PYTHON_THREADPOOL_THREAD_COUNT,
                    PYTHON_THREADPOOL_THREAD_COUNT_MIN)
                return False
            return True

        # Starting Python 3.9, worker won't be putting a limit on the
        # max_workers count in the created threadpool.
        default_value = None if sys.version_info.minor == 9 \
            else f'{PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT}'

        max_workers = get_app_setting(setting=PYTHON_THREADPOOL_THREAD_COUNT,
                                      default_value=default_value,
                                      validator=tp_max_workers_validator)

        if sys.version_info.minor <= 7:
            max_workers = min(int(max_workers),
                              PYTHON_THREADPOOL_THREAD_COUNT_MAX_37)

        # We can box the app setting as int for earlier python versions.
        return int(max_workers) if max_workers else None

    def _create_sync_call_tp(
            self, max_worker: Optional[int]) -> concurrent.futures.Executor:
        """Create a thread pool executor with max_worker. This is a wrapper
        over ThreadPoolExecutor constructor. Consider calling this method after
        _stop_sync_call_tp() to ensure only 1 synchronous thread pool is
        running.
        """
        return concurrent.futures.ThreadPoolExecutor(
            max_workers=max_worker
        )

    def _run_sync_func(self, invocation_id, context, func, params):
        # This helper exists because we need to access the current
        # invocation_id from ThreadPoolExecutor's threads.
        context.thread_local_storage.invocation_id = invocation_id
        try:
            return ExtensionManager.get_sync_invocation_wrapper(context,
                                                                func)(params)
        finally:
            context.thread_local_storage.invocation_id = None

    async def _run_async_func(self, context, func, params):
        return await ExtensionManager.get_async_invocation_wrapper(
            context, func, params
        )

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
            error_logger.exception(
                'unhandled error in gRPC thread. Exception: {0}'.format(
                    format_exception(ex)))
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

    return getattr(_invocation_id_local, 'invocation_id', None)


_invocation_id_local = threading.local()
