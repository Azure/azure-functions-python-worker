# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import logging
import os
import sys

from typing import List, Optional

from .functions import FunctionInfo, Registry
from .http_v2 import (
    HttpServerInitError,
    HttpV2Registry,
    http_coordinator,
    initialize_http_server,
    sync_http_request,
)
from .loader import index_function_app, process_indexed_function
from .logging import logger
from .otel import otel_manager, initialize_azure_monitor, configure_opentelemetry

from .bindings.context import get_context
from .bindings.meta import (load_binding_registry, is_trigger_binding,
                            from_incoming_proto, to_outgoing_param_binding,
                            to_outgoing_proto)
from .bindings.out import Out
from .utils.constants import (FUNCTION_DATA_CACHE,
                              RAW_HTTP_BODY_BYTES,
                              TYPED_DATA_COLLECTION,
                              RPC_HTTP_BODY_ONLY,
                              WORKER_STATUS,
                              RPC_HTTP_TRIGGER_METADATA_REMOVED,
                              SHARED_MEMORY_DATA_TRANSFER,
                              TRUE,
                              PYTHON_ENABLE_OPENTELEMETRY,
                              PYTHON_ENABLE_OPENTELEMETRY_DEFAULT,
                              WORKER_OPEN_TELEMETRY_ENABLED,
                              PYTHON_ENABLE_INIT_INDEXING,
                              HTTP_URI,
                              REQUIRES_ROUTE_PARAMETERS,
                              PYTHON_SCRIPT_FILE_NAME,
                              PYTHON_SCRIPT_FILE_NAME_DEFAULT,
                              PYTHON_ENABLE_DEBUG_LOGGING)
from .utils.current import get_current_loop, execute, run_sync_func
from .utils.env_state import get_app_setting, is_envvar_true
from .utils.helpers import change_cwd, get_worker_metadata
from .utils.tracing import serialize_exception
from .utils.validators import validate_script_file_name

metadata_result: Optional[List] = None
metadata_exception: Optional[Exception] = None
result = None  # Todo: type is coroutine?
_functions = Registry()
_function_data_cache_enabled: bool = False
_host: str = ""
protos = None


async def worker_init_request(request):
    logger.info("Library Worker: received worker_init_request")
    global result, _host, protos, _function_data_cache_enabled
    init_request = request.request.worker_init_request
    host_capabilities = init_request.capabilities
    _host = request.properties.get("host")
    protos = request.properties.get("protos")
    if FUNCTION_DATA_CACHE in host_capabilities:
        val = host_capabilities[FUNCTION_DATA_CACHE]
        _function_data_cache_enabled = val == TRUE

    capabilities = {
        RAW_HTTP_BODY_BYTES: TRUE,
        TYPED_DATA_COLLECTION: TRUE,
        RPC_HTTP_BODY_ONLY: TRUE,
        WORKER_STATUS: TRUE,
        RPC_HTTP_TRIGGER_METADATA_REMOVED: TRUE,
        SHARED_MEMORY_DATA_TRANSFER: TRUE,
    }
    if get_app_setting(setting=PYTHON_ENABLE_OPENTELEMETRY,
                       default_value=PYTHON_ENABLE_OPENTELEMETRY_DEFAULT):
        initialize_azure_monitor()

        if otel_manager.get_azure_monitor_available():
            capabilities[WORKER_OPEN_TELEMETRY_ENABLED] = TRUE

    # loading bindings registry and saving results to a static
    # dictionary which will be later used in the invocation request
    load_binding_registry()

    try:
        result = asyncio.create_task(load_function_metadata(
            init_request.function_app_directory,
            caller_info="worker_init_request"))
        if get_app_setting(setting=PYTHON_ENABLE_INIT_INDEXING):
            capabilities[HTTP_URI] = \
                initialize_http_server(_host)
            capabilities[REQUIRES_ROUTE_PARAMETERS] = TRUE
    except HttpServerInitError:
        raise
    except Exception as ex:
        # This is catching an exception that happens during indexing while the init
        # request is still in progress. The proxy worker will do nothing with this,
        # but metadata will fail
        global metadata_exception
        metadata_exception = ex

    return protos.WorkerInitResponse(
        capabilities=capabilities,
        worker_metadata=get_worker_metadata(protos),
        result=protos.StatusResult(status=protos.StatusResult.Success)
    )


# worker_status_request can be done in the proxy worker

async def functions_metadata_request(request):
    logger.info("Library Worker: received worker_metadata_request")
    global protos
    # Todo: should there be a check on if result is None?
    global result, metadata_result, metadata_exception
    if result:
        await result

    if metadata_exception:
        return protos.FunctionMetadataResponse(
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(
                    metadata_exception, protos)))

    else:
        return protos.FunctionMetadataResponse(
            use_default_metadata_indexing=False,
            function_metadata_results=metadata_result,
            result=protos.StatusResult(
                status=protos.StatusResult.Success))


async def functions_load_request(request):
    logger.info("Library Worker: received worker_load_request")
    global protos
    func_request = request.request.function_load_request
    function_id = func_request.function_id

    return protos.FunctionLoadResponse(
        function_id=function_id,
        result=protos.StatusResult(
            status=protos.StatusResult.Success))


async def invocation_request(request):
    logger.info("Library Worker: received worker_invocation_request")
    global protos
    invoc_request = request.request.invocation_request
    invocation_id = invoc_request.invocation_id
    function_id = invoc_request.function_id
    http_v2_enabled = False
    threadpool = request.properties.get("threadpool")

    try:
        fi: FunctionInfo = _functions.get_function(
            function_id)
        assert fi is not None

        args = {}

        http_v2_enabled = _functions.get_function(
            function_id).is_http_func and \
            HttpV2Registry.http_v2_enabled()

        for pb in invoc_request.input_data:
            pb_type_info = fi.input_types[pb.name]
            if is_trigger_binding(pb_type_info.binding_name):
                trigger_metadata = invoc_request.trigger_metadata
            else:
                trigger_metadata = None

            args[pb.name] = from_incoming_proto(
                pb_type_info.binding_name,
                pb,
                trigger_metadata=trigger_metadata,
                pytype=pb_type_info.pytype,
                function_name=_functions.get_function(
                    function_id).name,
                is_deferred_binding=pb_type_info.deferred_bindings_enabled)

        if http_v2_enabled:
            http_request = await http_coordinator.get_http_request_async(
                invocation_id)

            trigger_arg_name = fi.trigger_metadata.get('param_name')
            func_http_request = args[trigger_arg_name]
            await sync_http_request(http_request, func_http_request)
            args[trigger_arg_name] = http_request

        fi_context = get_context(invoc_request, fi.name,
                                 fi.directory)

        # Use local thread storage to store the invocation ID
        # for a customer's threads
        fi_context.thread_local_storage.invocation_id = invocation_id
        if fi.requires_context:
            args['context'] = fi_context

        if fi.output_types:
            for name in fi.output_types:
                args[name] = Out()

        if fi.is_async:
            if otel_manager.get_azure_monitor_available():
                configure_opentelemetry(fi_context)

            call_result = await execute(fi.func, **args)  # Not supporting Extensions
        else:
            _loop = get_current_loop()
            call_result = await _loop.run_in_executor(
                threadpool,
                run_sync_func,
                invocation_id, fi_context, fi.func, args)

        if call_result is not None and not fi.has_return:
            raise RuntimeError(
                f'function {fi.name!r} without a $return binding'
                'returned a non-None value')

        if http_v2_enabled:
            http_coordinator.set_http_response(invocation_id, call_result)

        output_data = []
        if fi.output_types:
            for out_name, out_type_info in fi.output_types.items():
                val = args[out_name].get()
                if val is None:
                    # TODO: is the "Out" parameter optional?
                    # Can "None" be marshaled into protos.TypedData?
                    continue

                param_binding = to_outgoing_param_binding(
                    out_type_info.binding_name, val,
                    pytype=out_type_info.pytype,
                    out_name=out_name,
                    protos=protos)
                output_data.append(param_binding)

        return_value = None
        if fi.return_type is not None and not http_v2_enabled:
            return_value = to_outgoing_proto(
                fi.return_type.binding_name,
                call_result,
                pytype=fi.return_type.pytype,
                protos=protos
            )

        # Actively flush customer print() function to console
        sys.stdout.flush()
        return protos.InvocationResponse(
            invocation_id=invocation_id,
            return_value=return_value,
            result=protos.StatusResult(
                status=protos.StatusResult.Success),
            output_data=output_data)

    except Exception as ex:
        if http_v2_enabled:
            http_coordinator.set_http_response(invocation_id, ex)
        global metadata_result
        metadata_result = ex
        return protos.InvocationResponse(
            invocation_id=invocation_id,
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(ex)))


async def function_environment_reload_request(request):
    """Only runs on Linux Consumption placeholder specialization.
    This is called only when placeholder mode is true. On worker restarts
    worker init request will be called directly.
    """
    logger.info("Library Worker: received worker_env_reload_request")
    try:

        func_env_reload_request = \
            request.request.function_environment_reload_request
        directory = func_env_reload_request.function_app_directory

        if is_envvar_true(PYTHON_ENABLE_DEBUG_LOGGING):
            root_logger = logging.getLogger("azure.functions")
            root_logger.setLevel(logging.DEBUG)

        # calling load_binding_registry again since the
        # reload_customer_libraries call clears the registry
        load_binding_registry()

        capabilities = {}
        if get_app_setting(
                setting=PYTHON_ENABLE_OPENTELEMETRY,
                default_value=PYTHON_ENABLE_OPENTELEMETRY_DEFAULT):
            initialize_azure_monitor()

            if otel_manager.get_azure_monitor_available():
                capabilities[WORKER_OPEN_TELEMETRY_ENABLED] = (
                    TRUE)

        try:
            global _host, result, protos
            _host = request.properties.get("host")
            protos = request.properties.get("protos")
            result = asyncio.create_task(load_function_metadata(
                directory,
                caller_info="environment_reload_request"))
            if get_app_setting(setting=PYTHON_ENABLE_INIT_INDEXING):
                capabilities[HTTP_URI] = \
                    initialize_http_server(_host)
                capabilities[REQUIRES_ROUTE_PARAMETERS] = TRUE
        except HttpServerInitError:
            raise

        # Change function app directory
        if getattr(func_env_reload_request,
                   'function_app_directory', None):
            change_cwd(
                func_env_reload_request.function_app_directory)

        return protos.FunctionEnvironmentReloadResponse(
            capabilities=capabilities,
            worker_metadata=get_worker_metadata(protos),
            result=protos.StatusResult(
                status=protos.StatusResult.Success))

    except Exception as ex:
        global metadata_exception
        metadata_exception = ex
        return protos.FunctionEnvironmentReloadResponse(
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(ex)))


async def load_function_metadata(function_app_directory, caller_info):
    global protos
    """
    This method is called to index the functions in the function app
    directory and save the results in function_metadata_result or
    function_metadata_exception in case of an exception.
    """
    try:
        script_file_name = get_app_setting(
            setting=PYTHON_SCRIPT_FILE_NAME,
            default_value=f'{PYTHON_SCRIPT_FILE_NAME_DEFAULT}')

        logger.debug(
            'Received load metadata request from %s, '
            'script_file_name: %s',
            caller_info, script_file_name)

        validate_script_file_name(script_file_name)
        function_path = os.path.join(function_app_directory,
                                     script_file_name)

        # For V1, the function path will not exist and
        # return None.
        global metadata_result
        metadata_result = (index_functions(function_path, function_app_directory)) \
            if os.path.exists(function_path) else None
    except Exception as ex:
        global metadata_exception
        metadata_exception = ex


def index_functions(function_path: str, function_dir: str):
    global protos
    indexed_functions = index_function_app(function_path)
    logger.info(
        "Indexed function app and found %s functions",
        len(indexed_functions)
    )

    if indexed_functions:
        fx_metadata_results, fx_bindings_logs = (
            process_indexed_function(
                protos,
                _functions,
                indexed_functions,
                function_dir))

        indexed_function_logs: List[str] = []
        indexed_function_bindings_logs = []
        for func in indexed_functions:
            func_binding_logs = fx_bindings_logs.get(func)
            for binding in func.get_bindings():
                deferred_binding_info = func_binding_logs.get(
                    binding.name)\
                    if func_binding_logs.get(binding.name) else ""
                indexed_function_bindings_logs.append((
                    binding.type, binding.name, deferred_binding_info))

            function_log = "Function Name: {}, Function Binding: {}" \
                .format(func.get_function_name(),
                        indexed_function_bindings_logs)
            indexed_function_logs.append(function_log)

        logger.info(
            'Successfully processed FunctionMetadataRequest for '
            'functions: %s. Deferred bindings enabled: %s.', " ".join(
                indexed_function_logs),
            _functions.deferred_bindings_enabled())

        return fx_metadata_results
