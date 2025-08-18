# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import logging
import os
import sys

from typing import List, MutableMapping, Optional

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
from .otel import otel_manager, configure_opentelemetry, initialize_azure_monitor
from .version import VERSION

from .bindings.context import get_context
from .bindings.meta import (from_incoming_proto,
                            is_trigger_binding,
                            load_binding_registry,
                            to_outgoing_param_binding,
                            to_outgoing_proto)
from .bindings.out import Out
from .utils.app_setting_manager import (get_app_setting,
                                        get_python_appsetting_state,
                                        is_envvar_true)
from .utils.constants import (FUNCTION_DATA_CACHE,
                              HTTP_URI,
                              PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY,
                              PYTHON_ENABLE_DEBUG_LOGGING,
                              PYTHON_ENABLE_OPENTELEMETRY,
                              PYTHON_SCRIPT_FILE_NAME,
                              PYTHON_SCRIPT_FILE_NAME_DEFAULT,
                              RAW_HTTP_BODY_BYTES,
                              REQUIRES_ROUTE_PARAMETERS,
                              RPC_HTTP_BODY_ONLY,
                              RPC_HTTP_TRIGGER_METADATA_REMOVED,
                              SHARED_MEMORY_DATA_TRANSFER,
                              TRUE,
                              TYPED_DATA_COLLECTION,
                              WORKER_OPEN_TELEMETRY_ENABLED,
                              WORKER_STATUS)
from .utils.executor import get_current_loop, execute_async, run_sync_func
from .utils.threadpool import get_threadpool_executor
from .utils.helpers import change_cwd, get_sdk_version, get_worker_metadata
from .utils.tracing import serialize_exception
from .utils.validators import validate_script_file_name

_metadata_result: Optional[List] = None
_functions: MutableMapping[str, FunctionInfo] = Registry()
_function_data_cache_enabled: bool = False
_host: str = ""
protos = None


async def worker_init_request(request):
    logger.debug("V2 Library Worker: received WorkerInitRequest,"
                 "Version %s", VERSION)
    global _host, protos, _function_data_cache_enabled
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
    if is_envvar_true(PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY):
        initialize_azure_monitor()

    if is_envvar_true(PYTHON_ENABLE_OPENTELEMETRY):
        otel_manager.set_otel_libs_available(True)

    if (otel_manager.get_azure_monitor_available()
            or otel_manager.get_otel_libs_available()):
        capabilities[WORKER_OPEN_TELEMETRY_ENABLED] = TRUE

    # loading bindings registry and saving results to a static
    # dictionary which will be later used in the invocation request
    load_binding_registry()

    # Index in init by default. Fail if an exception occurs.
    try:
        load_function_metadata(
            init_request.function_app_directory,
            caller_info="worker_init_request")
        try:
            if HttpV2Registry.http_v2_enabled():
                logger.debug("Streaming enabled.")
                capabilities[HTTP_URI] = \
                    initialize_http_server(_host)
                capabilities[REQUIRES_ROUTE_PARAMETERS] = TRUE
        except HttpServerInitError as ex:
            return protos.WorkerInitResponse(
                capabilities=capabilities,
                worker_metadata=get_worker_metadata(protos),
                result=protos.StatusResult(
                    status=protos.StatusResult.Failure,
                    exception=serialize_exception(
                        ex, protos))
            )
    except Exception as ex:
        return protos.WorkerInitResponse(
            capabilities=capabilities,
            worker_metadata=get_worker_metadata(protos),
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(
                    ex, protos))
        )

    logger.debug("Successfully completed WorkerInitRequest")
    return protos.WorkerInitResponse(
        capabilities=capabilities,
        worker_metadata=get_worker_metadata(protos),
        result=protos.StatusResult(status=protos.StatusResult.Success)
    )


# worker_status_request can be done in the proxy worker

async def functions_metadata_request(request):
    global protos, _metadata_result
    logger.debug("V2 Library Worker: received WorkerMetadataRequest."
                 " Metadata Result: %s,"
                 " azure-functions version: %s",
                 _metadata_result, get_sdk_version())

    return protos.FunctionMetadataResponse(
        use_default_metadata_indexing=False,
        function_metadata_results=_metadata_result,
        result=protos.StatusResult(
            status=protos.StatusResult.Success))


async def function_load_request(request):
    logger.debug("V2 Library Worker: received WorkerLoadRequest")
    global protos
    func_request = request.request.function_load_request
    function_id = func_request.function_id

    return protos.FunctionLoadResponse(
        function_id=function_id,
        result=protos.StatusResult(
            status=protos.StatusResult.Success))


async def invocation_request(request):
    logger.debug("V2 Library Worker: received WorkerInvocationRequest")
    global protos
    invoc_request = request.request.invocation_request
    invocation_id = invoc_request.invocation_id
    function_id = invoc_request.function_id
    http_v2_enabled = False

    threadpool = get_threadpool_executor()
    logger.debug(
        "Invocation context prepared. Invocation ID: %s, Function ID: %s, "
        "Threadpool id: %s",
        invocation_id,
        function_id,
        id(threadpool) if threadpool else None,
    )

    try:
        fi: FunctionInfo = _functions.get_function(
            function_id)
        assert fi is not None
        logger.info("Function name: %s, Function Type: %s",
                    fi.name,
                    ("async" if fi.is_async else "sync"))

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
            if (otel_manager.get_azure_monitor_available()
                    or otel_manager.get_otel_libs_available()):
                configure_opentelemetry(fi_context)

            # Extensions are not supported
            call_result = await execute_async(fi.func, args)
        else:
            _loop = get_current_loop()
            call_result = await _loop.run_in_executor(
                threadpool,
                run_sync_func,
                invocation_id, fi_context, fi.func, args)

        if call_result is not None and not fi.has_return:
            raise RuntimeError(
                'function %s without a $return binding'
                'returned a non-None value', repr(fi.name))

        if http_v2_enabled:
            http_coordinator.set_http_response(invocation_id, call_result)

        output_data = []
        if fi.output_types:
            for out_name, out_type_info in fi.output_types.items():
                val = args[out_name].get()
                if val is None:
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
        logger.debug("Successfully completed WorkerInvocationRequest.")
        return protos.InvocationResponse(
            invocation_id=invocation_id,
            return_value=return_value,
            result=protos.StatusResult(
                status=protos.StatusResult.Success),
            output_data=output_data)

    except Exception as ex:
        if http_v2_enabled:
            http_coordinator.set_http_response(invocation_id, ex)
        return protos.InvocationResponse(
            invocation_id=invocation_id,
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(ex, protos)))


async def function_environment_reload_request(request):
    """Only runs on Linux Consumption placeholder specialization.
    This is called only when placeholder mode is true. On worker restarts
    worker init request will be called directly.
    """
    logger.debug("V2 Library Worker: received FunctionEnvironmentReloadRequest, "
                 "Version %s", VERSION)
    global _host, protos
    try:

        func_env_reload_request = \
            request.request.function_environment_reload_request
        directory = func_env_reload_request.function_app_directory

        if func_env_reload_request.function_app_directory:
            sys.path.append(func_env_reload_request.function_app_directory)

        # Clear sys.path import cache, reload all module from new sys.path
        sys.path_importer_cache.clear()

        # Reload environment variables
        os.environ.clear()
        env_vars = func_env_reload_request.environment_variables
        for var in env_vars:
            os.environ[var] = env_vars[var]

        # TODO: Apply PYTHON_THREADPOOL_THREAD_COUNT

        if is_envvar_true(PYTHON_ENABLE_DEBUG_LOGGING):
            root_logger = logging.getLogger("azure.functions")
            root_logger.setLevel(logging.DEBUG)

        # calling load_binding_registry again since the
        # reload_customer_libraries call clears the registry
        load_binding_registry()

        capabilities = {}
        if is_envvar_true(PYTHON_ENABLE_OPENTELEMETRY):
            otel_manager.set_otel_libs_available(True)

        if is_envvar_true(PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY):
            initialize_azure_monitor()

        if (otel_manager.get_azure_monitor_available()
                or otel_manager.get_otel_libs_available()):
            capabilities[WORKER_OPEN_TELEMETRY_ENABLED] = (
                TRUE)

        try:
            _host = request.properties.get("host")
            protos = request.properties.get("protos")
            load_function_metadata(
                directory,
                caller_info="environment_reload_request")
            if HttpV2Registry.http_v2_enabled():
                capabilities[HTTP_URI] = \
                    initialize_http_server(_host)
                capabilities[REQUIRES_ROUTE_PARAMETERS] = TRUE
        except HttpServerInitError as ex:
            return protos.FunctionEnvironmentReloadResponse(
                result=protos.StatusResult(
                    status=protos.StatusResult.Failure,
                    exception=serialize_exception(ex, protos)))

        # Change function app directory
        if getattr(func_env_reload_request,
                   'function_app_directory', None):
            change_cwd(
                func_env_reload_request.function_app_directory)

        logger.debug("Successfully completed WorkerEnvReloadRequest.")
        return protos.FunctionEnvironmentReloadResponse(
            capabilities=capabilities,
            worker_metadata=get_worker_metadata(protos),
            result=protos.StatusResult(
                status=protos.StatusResult.Success))

    except Exception as ex:
        return protos.FunctionEnvironmentReloadResponse(
            result=protos.StatusResult(
                status=protos.StatusResult.Failure,
                exception=serialize_exception(ex, protos)))


def load_function_metadata(function_app_directory, caller_info):
    global protos, _metadata_result
    """
    This method is called to index the functions in the function app
    directory and save the results in function_metadata_result.

    If an exception occurs during the indexing, it will be caught
    in the worker_init_request and returned as a failure
    status result.
    """
    script_file_name = get_app_setting(
        setting=PYTHON_SCRIPT_FILE_NAME,
        default_value=PYTHON_SCRIPT_FILE_NAME_DEFAULT)

    logger.debug(
        'Received load_function_metadata request from %s, '
        'script_file_name: %s',
        caller_info, script_file_name)

    validate_script_file_name(script_file_name)
    function_path = os.path.join(function_app_directory,
                                 script_file_name)

    # For V1, the function path will not exist and
    # return None.
    global _metadata_result
    _metadata_result = (index_functions(function_path, function_app_directory)) \
        if os.path.exists(function_path) else None


def index_functions(function_path: str, function_dir: str):
    global protos
    indexed_functions = index_function_app(function_path)

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

            function_log = ("Function Name: " + func.get_function_name()
                            + ", Function Binding: "
                            + str(indexed_function_bindings_logs))
            indexed_function_logs.append(function_log)

        log_data = {
            "message": "Successfully indexed function app.",
            "function_count": len(indexed_functions),
            "functions": " ".join(indexed_function_logs),
            "deferred_bindings_enabled": _functions.deferred_bindings_enabled(),
            "app_settings": get_python_appsetting_state(),
            "azure-functions version": get_sdk_version(),
        }
        logger.info(json.dumps(log_data))

        return fx_metadata_results
