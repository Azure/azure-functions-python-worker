# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from types import ModuleType
from typing import Any, Callable, List
import logging
import sys
import importlib
import functools
from .utils.common import is_python_version
from .utils.wrappers import enable_feature_by
from .constants import (
    PYTHON_ISOLATE_WORKER_DEPENDENCIES,
    PYTHON_ENABLE_WORKER_EXTENSIONS,
    PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT,
    PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39
)
from .logging import logger


def get_sdk_from_sys_path() -> ModuleType:
    """Get the azure.functions SDK from the latest sys.path defined.
    This is to ensure the extension loaded from SDK is actually coming from
    customer's site-packages.

    Returns
    -------
    ModuleType
        The azure.functions that is loaded from the first sys.path entry
    """
    if 'azure.functions' in sys.modules:
        sys.modules.pop('azure.functions')

    return importlib.import_module('azure.functions')


def is_extension_enabled_in_sdk(module: ModuleType) -> bool:
    """Check if the extension feature is enabled in particular azure.functions
    package.

    Parameters
    ----------
    module: ModuleType
        The azure.functions SDK module

    Returns
    -------
    bool
        True on azure.functions SDK supports extension registration
    """
    return getattr(module, 'FuncExtension', None) is not None


def get_sdk_version(module: ModuleType) -> str:
    """Check the version of azure.functions sdk.

    Parameters
    ----------
    module: ModuleType
        The azure.functions SDK module

    Returns
    -------
    str
        The SDK version that our customer has installed.
    """

    return getattr(module, '__version__', 'undefined')


@enable_feature_by(
    flag=PYTHON_ENABLE_WORKER_EXTENSIONS,
    flag_default=(
        PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39 if
        is_python_version('3.9') else
        PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT
    )
)
def invoke_extension(context, hook_name):
    """Helper to execute extensions. If one of the extension fails in the
    extension chain, the rest of them will continue, emitting an error log
    of an exception trace for failed extension.

    Parameters
    ----------
    context: azure.functions.Context
        Azure Functions context to be passed onto extension
    hook_name: str
        The exetension name to be executed (e.g. before_invocations).
        These are defined in azure.functions.FuncExtensionHooks.
    """

    sdk = get_sdk_from_sys_path()
    if not is_extension_enabled_in_sdk(sdk):
        logger.warning(f'The azure.functions ({get_sdk_version(sdk)}) does '
                       'not support Python worker extensions. If you believe '
                       'extensions are correctly installed, please set the '
                       f'{PYTHON_ISOLATE_WORKER_DEPENDENCIES} and '
                       f'{PYTHON_ENABLE_WORKER_EXTENSIONS} to "true"')
        return

    hooks = sdk.FuncExtension.get_hooks_of_trigger(context.function_name)
    for hook_meta in getattr(hooks, hook_name, []):
        ext_logger = logging.getLogger(hook_meta.ext_name)
        try:
            hook_meta.impl(ext_logger, context)
        except Exception as e:
            ext_logger.error(e, exc_info=True)


def raw_invocation_wrapper(context, function, args) -> Any:
    """Calls before_invocation and after_invocation extensions additional to
    function invocation"""
    invoke_extension(context, 'before_invocation')
    result = function(**args)
    invoke_extension(context, 'after_invocation')
    return result


def get_invocation_wrapper(context, function) -> Callable[[List], Any]:
    """Get a synchronous lambda of extension wrapped function which takes
    function parameters"""
    return functools.partial(raw_invocation_wrapper, context, function)


async def get_invocation_wrapper_async(context, function, args) -> Any:
    """An asynchronous coroutine for executing function with extensions"""
    invoke_extension(context, 'before_invocation')
    result = await function(**args)
    invoke_extension(context, 'after_invocation')
    return result
