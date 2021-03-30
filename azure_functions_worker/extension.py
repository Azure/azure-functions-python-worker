# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from types import ModuleType
from typing import Any, Callable, List, Optional
import sys
import importlib
import logging
import functools
from .utils.common import is_python_version
from .utils.wrappers import enable_feature_by
from .constants import (
    PYTHON_ISOLATE_WORKER_DEPENDENCIES,
    PYTHON_ENABLE_WORKER_EXTENSIONS,
    PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT,
    PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39
)
from .logging import logger, SYSTEM_LOG_PREFIX


# Extension Hooks
FUNC_EXT_POST_FUNCTION_LOAD = "post_function_load"
FUNC_EXT_PRE_INVOCATION = "pre_invocation"
FUNC_EXT_POST_INVOCATION = "post_invocation"
APP_EXT_POST_FUNCTION_LOAD = "post_function_load_app_level"
APP_EXT_PRE_INVOCATION = "pre_invocation_app_level"
APP_EXT_POST_INVOCATION = "post_invocation_app_level"


class ExtensionManager:
    """This marks if the ExtensionManager has already proceeded a detection,
    if so, the sdk will be cached in ._extension_enabled_sdk
    """
    _is_sdk_detected: bool = False

    """This is a cache of azure.functions module that supports extension
    interfaces. If this is None, that mean the sdk does not support extension.
    """
    _extension_enabled_sdk: Optional[ModuleType] = None

    @classmethod
    @enable_feature_by(
        flag=PYTHON_ENABLE_WORKER_EXTENSIONS,
        flag_default=(
            PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39 if
            is_python_version('3.9') else
            PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT
        )
    )
    def function_load_extension(cls, func_name, func_directory):
        """Helper to execute function load extensions. If one of the extension
        fails in the extension chain, the rest of them will continue, emitting
        an error log of an exception trace for failed extension.

        Parameters
        ----------
        func_name: str
            The name of the trigger (e.g. HttpTrigger)
        func_directory: str
            The folder path of the trigger
            (e.g. /home/site/wwwroot/HttpTrigger).
        """
        sdk = cls._try_get_sdk_with_extension_enabled()
        if sdk is None:
            return
        else:
            cls._info_discover_extension_list(func_name, sdk)

        # Invoke function hooks
        funcs = sdk.ExtensionMeta.get_function_hooks(func_name)
        cls._safe_execute_function_load_hooks(
            funcs, FUNC_EXT_POST_FUNCTION_LOAD, func_name, func_directory
        )

        # Invoke application hook
        apps = sdk.ExtensionMeta.get_application_hooks()
        cls._safe_execute_function_load_hooks(
            apps, APP_EXT_POST_FUNCTION_LOAD, func_name, func_directory
        )

    @classmethod
    @enable_feature_by(
        flag=PYTHON_ENABLE_WORKER_EXTENSIONS,
        flag_default=(
            PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39 if
            is_python_version('3.9') else
            PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT
        )
    )
    def invocation_extension(cls, ctx, hook_name, func_args, func_ret=None):
        """Helper to execute extensions. If one of the extension fails in the
        extension chain, the rest of them will continue, emitting an error log
        of an exception trace for failed extension.

        Parameters
        ----------
        ctx: azure.functions.Context
            Azure Functions context to be passed onto extension
        hook_name: str
            The exetension name to be executed (e.g. pre_invocations).
            These are defined in azure.functions.FuncExtensionHooks.
        """
        sdk = cls._try_get_sdk_with_extension_enabled()
        if sdk is None:
            return

        # Invoke function hooks
        funcs = sdk.ExtensionMeta.get_function_hooks(ctx.function_name)
        cls._safe_execute_invocation_hooks(
            funcs, hook_name, ctx, func_args, func_ret
        )

        # Invoke application hook
        apps = sdk.ExtensionMeta.get_application_hooks()
        cls._safe_execute_invocation_hooks(
            apps, hook_name, ctx, func_args, func_ret
        )

    @classmethod
    def get_invocation_wrapper(cls, ctx, function) -> Callable[[List], Any]:
        """Get a synchronous lambda of extension wrapped function which takes
        function parameters
        """
        return functools.partial(cls._raw_invocation_wrapper, ctx, function)

    @classmethod
    async def get_invocation_wrapper_async(cls, ctx, function, args) -> Any:
        """An asynchronous coroutine for executing function with extensions
        """
        cls.invocation_extension(ctx, APP_EXT_PRE_INVOCATION, args)
        cls.invocation_extension(ctx, FUNC_EXT_PRE_INVOCATION, args)
        result = await function(**args)
        cls.invocation_extension(ctx, FUNC_EXT_POST_INVOCATION, args, result)
        cls.invocation_extension(ctx, APP_EXT_POST_INVOCATION, args, result)
        return result

    @staticmethod
    def _get_sdk_from_sys_path() -> ModuleType:
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

    @staticmethod
    def _is_extension_enabled_in_sdk(module: ModuleType) -> bool:
        """Check if the extension feature is enabled in particular
        azure.functions package.

        Parameters
        ----------
        module: ModuleType
            The azure.functions SDK module

        Returns
        -------
        bool
            True on azure.functions SDK supports extension registration
        """
        return getattr(module, 'ExtensionMeta', None) is not None

    @staticmethod
    def _get_sdk_version(module: ModuleType) -> str:
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

    @classmethod
    def _is_pre_invocation_hook(cls, name) -> bool:
        return name in (FUNC_EXT_PRE_INVOCATION, APP_EXT_PRE_INVOCATION)

    @classmethod
    def _is_post_invocation_hook(cls, name) -> bool:
        return name in (FUNC_EXT_POST_INVOCATION, APP_EXT_POST_INVOCATION)

    @classmethod
    def _safe_execute_invocation_hooks(cls, hooks, hook_name, ctx, fargs, fret):
        if hooks:
            for hook_meta in getattr(hooks, hook_name, []):
                # Register a system logger with prefix azure_functions_worker
                ext_logger = logging.getLogger(
                    f'{SYSTEM_LOG_PREFIX}.extension.{hook_meta.ext_name}'
                )
                try:
                    if cls._is_pre_invocation_hook(hook_name):
                        hook_meta.ext_impl(ext_logger, ctx, fargs)
                    elif cls._is_post_invocation_hook(hook_name):
                        hook_meta.ext_impl(ext_logger, ctx, fargs, fret)
                except Exception as e:
                    ext_logger.error(e, exc_info=True)

    @classmethod
    def _safe_execute_function_load_hooks(cls, hooks, hook_name, fname, fdir):
        if hooks:
            for hook_meta in getattr(hooks, hook_name, []):
                try:
                    hook_meta.ext_impl(fname, fdir)
                except Exception as e:
                    logger.error(e, exc_info=True)

    @classmethod
    def _raw_invocation_wrapper(cls, ctx, function, args) -> Any:
        """Calls pre_invocation and post_invocation extensions additional
        to function invocation
        """
        cls.invocation_extension(ctx, APP_EXT_PRE_INVOCATION, args)
        cls.invocation_extension(ctx, FUNC_EXT_PRE_INVOCATION, args)
        result = function(**args)
        cls.invocation_extension(ctx, FUNC_EXT_POST_INVOCATION, args, result)
        cls.invocation_extension(ctx, APP_EXT_POST_INVOCATION, args, result)
        return result

    @classmethod
    def _try_get_sdk_with_extension_enabled(cls) -> Optional[ModuleType]:
        if cls._is_sdk_detected:
            return cls._extension_enabled_sdk

        sdk = cls._get_sdk_from_sys_path()
        if cls._is_extension_enabled_in_sdk(sdk):
            cls._info_extension_is_enabled(sdk)
            cls._extension_enabled_sdk = sdk
        else:
            cls._warn_sdk_not_support_extension(sdk)
            cls._extension_enabled_sdk = None

        cls._is_sdk_detected = True
        return cls._extension_enabled_sdk

    @classmethod
    def _info_extension_is_enabled(cls, sdk):
        logger.info(
            'Python Worker Extension is enabled in azure.functions '
            f'({cls._get_sdk_version(sdk)}).'
        )

    @classmethod
    def _info_discover_extension_list(cls, function_name, sdk):
        logger.info(
            f'Python Worker Extension Manager is loading {function_name}, '
            'current registered extensions: '
            f'{sdk.ExtensionMeta.get_registered_extensions_json()}'
        )

    @classmethod
    def _warn_sdk_not_support_extension(cls, sdk):
        logger.warning(
            f'The azure.functions ({cls._get_sdk_version(sdk)}) does not '
            'support Python worker extensions. If you believe extensions '
            'are correctly installed, please set the '
            f'{PYTHON_ISOLATE_WORKER_DEPENDENCIES} and '
            f'{PYTHON_ENABLE_WORKER_EXTENSIONS} to "true"'
        )

    @classmethod
    def _warn_context_has_no_function_name(cls):
        logger.warning(
            'Extension manager fails to execute invocation life-cycles. '
            'Property .function_name is not found in context'
        )
