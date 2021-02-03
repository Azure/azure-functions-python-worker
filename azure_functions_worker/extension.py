# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from types import ModuleType
from typing import Any, Callable, List
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
from .logging import logger


class ExtensionManager:
    @staticmethod
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

    @staticmethod
    def is_extension_enabled_in_sdk(module: ModuleType) -> bool:
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
        sdk = cls.get_sdk_from_sys_path()
        if not cls.is_extension_enabled_in_sdk(sdk):
            cls._warn_extension_is_not_enabled_in_sdk(sdk)
            return

        # Invoke function hooks
        funcs = sdk.ExtensionMeta.get_function_hooks(func_name)
        cls.safe_execute_function_load_hooks(
            funcs, 'post_function_load', func_name, func_directory
        )

        # Invoke application hook
        apps = sdk.ExtensionMeta.get_applicaiton_hooks()
        cls.safe_execute_function_load_hooks(
            apps, 'post_function_load_app_level', func_name, func_directory
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
        sdk = cls.get_sdk_from_sys_path()
        if not cls.is_extension_enabled_in_sdk(sdk):
            cls._warn_extension_is_not_enabled_in_sdk(sdk)
            return

        # Invoke function hooks
        funcs = sdk.ExtensionMeta.get_function_hooks(ctx.function_name)
        cls.safe_execute_invocation_hooks(
            funcs, hook_name, ctx, func_args, func_ret
        )

        # Invoke application hook
        apps = sdk.ExtensionMeta.get_applicaiton_hooks()
        cls.safe_execute_invocation_hooks(
            apps, hook_name, ctx, func_args, func_ret
        )

    @classmethod
    def safe_execute_invocation_hooks(cls, hooks, hook_name, ctx, fargs, fret):
        if hooks:
            for hook_meta in getattr(hooks, hook_name, []):
                ext_logger = logging.getLogger(hook_meta.ext_name)
                try:
                    if cls._is_pre_invocation_hook(hook_name):
                        hook_meta.ext_impl(ext_logger, ctx, fargs)
                    elif cls._is_post_invocation_hook(hook_name):
                        hook_meta.ext_impl(ext_logger, ctx, fargs, fret)
                except Exception as e:
                    # Send error trace to customer logs
                    ext_logger.error(e, exc_info=True)
                    # Send error trace to system logs
                    logger.error(e, exc_info=True)

    @classmethod
    def safe_execute_function_load_hooks(cls, hooks, hook_name, fname, fdir):
        if hooks:
            for hook_meta in getattr(hooks, hook_name, []):
                hook_meta.ext_impl(fname, fdir)

    @classmethod
    def raw_invocation_wrapper(cls, ctx, function, args) -> Any:
        """Calls pre_invocation and post_invocation extensions additional
        to function invocation
        """
        cls.invocation_extension(ctx, 'pre_invocation_app_level', args)
        cls.invocation_extension(ctx, 'pre_invocation', args)
        result = function(**args)
        cls.invocation_extension(ctx, 'post_invocation', args, result)
        cls.invocation_extension(ctx, 'post_invocation_app_level', args, result)
        return result

    @classmethod
    def get_invocation_wrapper(cls, ctx, function) -> Callable[[List], Any]:
        """Get a synchronous lambda of extension wrapped function which takes
        function parameters
        """
        return functools.partial(cls.raw_invocation_wrapper, ctx, function)

    @classmethod
    async def get_invocation_wrapper_async(cls, ctx, function, args) -> Any:
        """An asynchronous coroutine for executing function with extensions"""
        cls.invocation_extension(ctx, 'pre_invocation_app_level', args)
        cls.invocation_extension(ctx, 'pre_invocation', args)
        result = await function(**args)
        cls.invocation_extension(ctx, 'post_invocation', args, result)
        cls.invocation_extension(ctx, 'post_invocation_app_level', args, result)
        return result

    @classmethod
    def _is_pre_invocation_hook(cls, name) -> bool:
        return name in ('pre_invocation', 'pre_invocation_app_level')

    @classmethod
    def _is_post_invocation_hook(cls, name) -> bool:
        return name in ('post_invocation', 'post_invocation_app_level')

    @classmethod
    def _warn_extension_is_not_enabled_in_sdk(cls, sdk):
        logger.warning(
            f'The azure.functions ({cls.get_sdk_version(sdk)}) does not '
            'support Python worker extensions. If you believe extensions '
            'are correctly installed, please set the '
            f'{PYTHON_ISOLATE_WORKER_DEPENDENCIES} and '
            f'{PYTHON_ENABLE_WORKER_EXTENSIONS} to "true"'
        )
