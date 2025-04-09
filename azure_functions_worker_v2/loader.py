# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import importlib
import importlib.machinery
import os.path
import pathlib
import sys
import time

from datetime import timedelta
from typing import Any, Dict, Optional, Union


from .functions import Registry
from .logging import logger

from .bindings.meta import get_deferred_raw_bindings
from .bindings.retrycontext import RetryPolicy
from .utils.constants import (
    CUSTOMER_PACKAGES_PATH,
    METADATA_PROPERTIES_WORKER_INDEXED,
    MODULE_NOT_FOUND_TS_URL,
    PYTHON_LANGUAGE_RUNTIME,
    PYTHON_SCRIPT_FILE_NAME,
    PYTHON_SCRIPT_FILE_NAME_DEFAULT,
    RETRY_POLICY,
)
from .utils.env_state import get_app_setting
from .utils.wrappers import attach_message_to_exception

_AZURE_NAMESPACE = '__app__'
_DEFAULT_SCRIPT_FILENAME = '__init__.py'
_DEFAULT_ENTRY_POINT = 'main'
_submodule_dirsL: list[Any] = []


def convert_to_seconds(timestr: str):
    x = time.strptime(timestr, '%H:%M:%S')
    return int(timedelta(hours=x.tm_hour, minutes=x.tm_min,
                         seconds=x.tm_sec).total_seconds())


def build_binding_protos(protos, indexed_function) -> Dict:
    binding_protos = {}
    for binding in indexed_function.get_bindings():
        binding_protos[binding.name] = protos.BindingInfo(
            type=binding.type,
            data_type=binding.data_type,
            direction=binding.direction)

    return binding_protos


def build_retry_protos(protos, indexed_function) -> Union[Dict, None]:
    retry = get_retry_settings(indexed_function)

    if not retry:
        return None

    strategy = retry.get(RetryPolicy.STRATEGY.value)
    max_retry_count = int(retry.get(RetryPolicy.MAX_RETRY_COUNT.value))
    retry_strategy = retry.get(RetryPolicy.STRATEGY.value)

    if strategy == "fixed_delay":
        return build_fixed_delay_retry(protos, retry, max_retry_count, retry_strategy)
    else:
        return build_variable_interval_retry(protos, retry, max_retry_count,
                                             retry_strategy)


def get_retry_settings(indexed_function):
    try:
        return indexed_function.get_settings_dict(RETRY_POLICY)
    except AttributeError as e:
        logger.warning("AttributeError while loading retry policy. %s", e)
        return None


def build_fixed_delay_retry(protos, retry, max_retry_count, retry_strategy):
    delay_interval = protos.Duration(
        seconds=convert_to_seconds(retry.get(RetryPolicy.DELAY_INTERVAL.value))
    )
    return protos.RpcRetryOptions(
        max_retry_count=max_retry_count,
        retry_strategy=retry_strategy,
        delay_interval=delay_interval,
    )


def build_variable_interval_retry(protos, retry, max_retry_count, retry_strategy):
    minimum_interval = protos.Duration(
        seconds=convert_to_seconds(
            retry.get(RetryPolicy.MINIMUM_INTERVAL.value))
    )
    maximum_interval = protos.Duration(
        seconds=convert_to_seconds(
            retry.get(RetryPolicy.MAXIMUM_INTERVAL.value))
    )
    return protos.RpcRetryOptions(
        max_retry_count=max_retry_count,
        retry_strategy=retry_strategy,
        minimum_interval=minimum_interval,
        maximum_interval=maximum_interval
    )


def process_indexed_function(protos,
                             functions_registry: Registry,
                             indexed_functions, function_dir):
    """
    fx_metadata_results is a list of the RpcFunctionMetadata for
    all the functions in the particular app.

    fx_binding_logs represents a dictionary of each function in
    the app and its corresponding bindings. The raw bindings and
    binding logs are generated from the base extension if the
    function is using deferred bindings. If not, the raw bindings
    come from the azure-functions sdk and no additional binding
    logs are generated.
    """
    fx_metadata_results = []
    fx_bindings_logs = {}
    for indexed_function in indexed_functions:
        function_info = functions_registry.add_indexed_function(
            function=indexed_function, protos=protos)

        binding_protos = build_binding_protos(protos, indexed_function)
        retry_protos = build_retry_protos(protos, indexed_function)

        raw_bindings, bindings_logs = get_fx_raw_bindings(
            indexed_function=indexed_function,
            function_info=function_info)

        function_metadata = protos.RpcFunctionMetadata(
            name=function_info.name,
            function_id=function_info.function_id,
            managed_dependency_enabled=False,  # only enabled for PowerShell
            directory=function_dir,
            script_file=indexed_function.function_script_file,
            entry_point=function_info.name,
            is_proxy=False,  # not supported in V4
            language=PYTHON_LANGUAGE_RUNTIME,
            bindings=binding_protos,
            raw_bindings=raw_bindings,
            retry_options=retry_protos,
            properties={METADATA_PROPERTIES_WORKER_INDEXED: "True"})

        fx_bindings_logs.update({indexed_function: bindings_logs})
        fx_metadata_results.append(function_metadata)

    return fx_metadata_results, fx_bindings_logs


@attach_message_to_exception(
    expt_type=ImportError,
    message="Cannot find module. Please check the requirements.txt file for the "
            "missing module. For more info, please refer the troubleshooting guide: "
            + MODULE_NOT_FOUND_TS_URL + ". Current sys.path: " + " ".join(sys.path),
    debug_logs="Error in index_function_app. Sys Path:" + " ".join(sys.path)
               + ", python-packages Path exists: "
               + str(os.path.exists(CUSTOMER_PACKAGES_PATH)))
def index_function_app(function_path: str):
    module_name = pathlib.Path(function_path).stem
    imported_module = importlib.import_module(module_name)

    from azure.functions import FunctionRegister
    app: Optional[FunctionRegister] = None
    for i in imported_module.__dir__():
        if isinstance(getattr(imported_module, i, None), FunctionRegister):
            if not app:
                app = getattr(imported_module, i, None)
            else:
                raise ValueError(
                    "More than one %s or other top "
                    "level function app instances are defined.", app.__class__.__name__)

    if not app:
        script_file_name = get_app_setting(
            setting=PYTHON_SCRIPT_FILE_NAME,
            default_value=PYTHON_SCRIPT_FILE_NAME_DEFAULT)
        raise ValueError("Could not find top level function app instances in %s.",
                         script_file_name)

    return app.get_functions()


def get_fx_raw_bindings(indexed_function, function_info):
    """
    If deferred bindings is enabled at the function level,
    raw bindings are generated through the base extension.
    This method returns two things: the raw bindings for that
    function and a dict the corresponding logs.


    If not, raw bindings are generated through azure-functions.
    An empty dict is returned as we are not logging any
    additional information if deferred bindings is not enabled
    for this function.
    """
    if function_info.deferred_bindings_enabled:
        raw_bindings, bindings_logs = get_deferred_raw_bindings(
            indexed_function, function_info.input_types)
        return raw_bindings, bindings_logs

    else:
        return indexed_function.get_raw_bindings(), {}
