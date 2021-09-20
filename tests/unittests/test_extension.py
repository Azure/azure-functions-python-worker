# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import os
import sys
import unittest
from unittest.mock import patch, Mock, call
from importlib import import_module
from azure_functions_worker._thirdparty import aio_compat
from azure_functions_worker.extension import (
    ExtensionManager,
    APP_EXT_POST_FUNCTION_LOAD, FUNC_EXT_POST_FUNCTION_LOAD,
    APP_EXT_PRE_INVOCATION, FUNC_EXT_PRE_INVOCATION,
    APP_EXT_POST_INVOCATION, FUNC_EXT_POST_INVOCATION
)
from azure_functions_worker.utils.common import get_sdk_from_sys_path
from azure_functions_worker.constants import PYTHON_ENABLE_WORKER_EXTENSIONS


class MockContext:
    def __init__(self, function_name: str, function_directory: str):
        self.function_name = function_name
        self.function_directory = function_directory


class TestExtension(unittest.TestCase):

    def setUp(self):
        # Patch sys.modules and sys.path to avoid pollution between tests
        self.mock_environ = patch.dict('os.environ', os.environ.copy())
        self.mock_sys_module = patch.dict('sys.modules', sys.modules.copy())
        self.mock_sys_path = patch('sys.path', sys.path.copy())
        self.mock_environ.start()
        self.mock_sys_module.start()
        self.mock_sys_path.start()

        # Initialize Extension Manager Instance
        self._instance = ExtensionManager
        self._instance._is_sdk_detected = False
        self._instance._extension_enabled_sdk = None

        # Initialize Azure Functions SDK and clear cache
        self._sdk = import_module('azure.functions')
        self._sdk.ExtensionMeta._func_exts = {}
        self._sdk.ExtensionMeta._app_exts = None
        self._sdk.ExtensionMeta._info = {}
        sys.modules.pop('azure.functions')
        sys.modules.pop('azure')

        # Derived dummy SDK Python system path
        self._dummy_sdk_sys_path = os.path.join(
            os.path.dirname(__file__),
            'resources',
            'mock_azure_functions'
        )

        # Initialize mock context
        self._mock_arguments = {'req': 'request'}
        self._mock_func_name = 'HttpTrigger'
        self._mock_func_dir = '/home/site/wwwroot/HttpTrigger'
        self._mock_context = MockContext(
            function_name=self._mock_func_name,
            function_directory=self._mock_func_dir
        )

        # Set feature flag to on
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'true'

    def tearDown(self) -> None:
        os.environ.pop(PYTHON_ENABLE_WORKER_EXTENSIONS)

        self.mock_sys_path.stop()
        self.mock_sys_module.stop()
        self.mock_environ.stop()

    def test_extension_is_supported_by_latest_sdk(self):
        """Test if extension interface supports check as expected on
        new version of azure.functions SDK
        """
        module = get_sdk_from_sys_path()
        sdk_enabled = self._instance._is_extension_enabled_in_sdk(module)
        self.assertTrue(sdk_enabled)

    def test_extension_is_not_supported_by_mock_sdk(self):
        """Test if the detection works when an azure.functions SDK does not
        support extension management.
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        module = get_sdk_from_sys_path()
        sdk_enabled = self._instance._is_extension_enabled_in_sdk(module)
        self.assertFalse(sdk_enabled)

    @patch('azure_functions_worker.extension.get_sdk_from_sys_path')
    def test_function_load_extension_enable_when_feature_flag_is_on(
        self,
        get_sdk_from_sys_path_mock: Mock
    ):
        """When turning off the feature flag PYTHON_ENABLE_WORKER_EXTENSIONS,
        the post_function_load extension should be disabled
        """
        self._instance.function_load_extension(
            func_name=self._mock_func_name,
            func_directory=self._mock_func_dir
        )
        get_sdk_from_sys_path_mock.assert_called_once()

    @patch('azure_functions_worker.extension.get_sdk_from_sys_path')
    def test_function_load_extension_disable_when_feature_flag_is_off(
        self,
        get_sdk_from_sys_path_mock: Mock
    ):
        """When turning off the feature flag PYTHON_ENABLE_WORKER_EXTENSIONS,
        the post_function_load extension should be disabled
        """
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'false'
        self._instance.function_load_extension(
            func_name=self._mock_func_name,
            func_directory=self._mock_func_dir
        )
        get_sdk_from_sys_path_mock.assert_not_called()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_warn_sdk_not_support_extension')
    def test_function_load_extension_warns_when_sdk_does_not_support(
        self,
        _warn_sdk_not_support_extension_mock: Mock
    ):
        """When customer is using an old version of sdk which does not have
        extension support and turning on the feature flag, we should warn them
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        self._instance.function_load_extension(
            func_name=self._mock_func_name,
            func_directory=self._mock_func_dir
        )
        _warn_sdk_not_support_extension_mock.assert_called_once()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_safe_execute_function_load_hooks')
    def test_function_load_extension_should_invoke_extension_call(
        self,
        safe_execute_function_load_hooks_mock: Mock
    ):
        """Should invoke extension if SDK suports extension interface
        """
        self._instance.function_load_extension(
            func_name=self._mock_func_name,
            func_directory=self._mock_func_dir
        )
        # No registered hooks
        safe_execute_function_load_hooks_mock.assert_has_calls(
            calls=[
                call(
                    None, APP_EXT_POST_FUNCTION_LOAD,
                    self._mock_func_name, self._mock_func_dir
                ),
                call(
                    None, FUNC_EXT_POST_FUNCTION_LOAD,
                    self._mock_func_name, self._mock_func_dir
                )
            ],
            any_order=True
        )

    @patch('azure_functions_worker.extension.get_sdk_from_sys_path')
    def test_invocation_extension_enable_when_feature_flag_is_on(
        self,
        get_sdk_from_sys_path_mock: Mock
    ):
        """When turning off the feature flag PYTHON_ENABLE_WORKER_EXTENSIONS,
        the pre_invocation and post_invocation extension should be disabled
        """
        self._instance._invocation_extension(
            ctx=self._mock_context,
            hook_name=FUNC_EXT_PRE_INVOCATION,
            func_args=[],
            func_ret=None
        )
        get_sdk_from_sys_path_mock.assert_called_once()

    @patch('azure_functions_worker.extension.get_sdk_from_sys_path')
    def test_invocation_extension_extension_disable_when_feature_flag_is_off(
        self,
        get_sdk_from_sys_path_mock: Mock
    ):
        """When turning off the feature flag PYTHON_ENABLE_WORKER_EXTENSIONS,
        the pre_invocation and post_invocation extension should be disabled
        """
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'false'
        self._instance._invocation_extension(
            ctx=self._mock_context,
            hook_name=FUNC_EXT_PRE_INVOCATION,
            func_args=[],
            func_ret=None
        )
        get_sdk_from_sys_path_mock.assert_not_called()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_warn_sdk_not_support_extension')
    def test_invocation_extension_warns_when_sdk_does_not_support(
        self,
        _warn_sdk_not_support_extension_mock: Mock
    ):
        """When customer is using an old version of sdk which does not have
        extension support and turning on the feature flag, we should warn them
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        self._instance._invocation_extension(
            ctx=self._mock_context,
            hook_name=FUNC_EXT_PRE_INVOCATION,
            func_args=[],
            func_ret=None
        )
        _warn_sdk_not_support_extension_mock.assert_called_once()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_safe_execute_invocation_hooks')
    def test_invocation_extension_should_invoke_extension_call(
        self,
        safe_execute_invocation_hooks_mock: Mock
    ):
        """Should invoke extension if SDK suports extension interface
        """
        for hook_name in (APP_EXT_PRE_INVOCATION, FUNC_EXT_PRE_INVOCATION,
                          APP_EXT_POST_INVOCATION, FUNC_EXT_POST_INVOCATION):
            self._instance._invocation_extension(
                ctx=self._mock_context,
                hook_name=hook_name,
                func_args=[],
                func_ret=None
            )

            safe_execute_invocation_hooks_mock.assert_has_calls(
                calls=[
                    call(
                        None, hook_name, self._mock_context,
                        [], None
                    )
                ],
                any_order=True
            )

    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_is_pre_invocation_hook')
    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_is_post_invocation_hook')
    def test_empty_hooks_should_not_receive_any_invocation(
        self,
        _is_post_invocation_hook_mock: Mock,
        _is_pre_invocation_hook_mock: Mock
    ):
        """If there is no life-cycle hooks implemented under a function,
        then we should skip it
        """
        for hook_name in (APP_EXT_PRE_INVOCATION, FUNC_EXT_PRE_INVOCATION,
                          APP_EXT_POST_INVOCATION, FUNC_EXT_POST_INVOCATION):
            self._instance._safe_execute_invocation_hooks(
                hooks=[],
                hook_name=hook_name,
                ctx=self._mock_context,
                fargs=[],
                fret=None
            )
            _is_pre_invocation_hook_mock.assert_not_called()
            _is_post_invocation_hook_mock.assert_not_called()

    def test_invocation_hooks_should_be_executed(self):
        """If there is an extension implemented the pre_invocation and
        post_invocation life-cycle hooks, it should be invoked in
        safe_execute_invocation_hooks
        """
        FuncExtClass = self._generate_new_func_extension_class(
            base=self._sdk.FuncExtensionBase,
            trigger=self._mock_func_name
        )
        func_ext_instance = FuncExtClass()
        hook_instances = (
            self._sdk.ExtensionMeta.get_function_hooks(self._mock_func_name)
        )
        for hook_name in (FUNC_EXT_PRE_INVOCATION, FUNC_EXT_POST_INVOCATION):
            self._instance._safe_execute_invocation_hooks(
                hooks=hook_instances,
                hook_name=hook_name,
                ctx=self._mock_context,
                fargs=[],
                fret=None
            )
        self.assertFalse(func_ext_instance._post_function_load_executed)
        self.assertTrue(func_ext_instance._pre_invocation_executed)
        self.assertTrue(func_ext_instance._post_invocation_executed)

    def test_post_function_load_hook_should_be_executed(self):
        """If there is an extension implemented the post_function_load
        life-cycle hook, it invokes in safe_execute_function_load_hooks
        """
        FuncExtClass = self._generate_new_func_extension_class(
            base=self._sdk.FuncExtensionBase,
            trigger=self._mock_func_name
        )
        func_ext_instance = FuncExtClass()
        hook_instances = (
            self._sdk.ExtensionMeta.get_function_hooks(self._mock_func_name)
        )
        for hook_name in (FUNC_EXT_POST_FUNCTION_LOAD,):
            self._instance._safe_execute_function_load_hooks(
                hooks=hook_instances,
                hook_name=hook_name,
                fname=self._mock_func_name,
                fdir=self._mock_func_dir
            )
        self.assertTrue(func_ext_instance._post_function_load_executed)
        self.assertFalse(func_ext_instance._pre_invocation_executed)
        self.assertFalse(func_ext_instance._post_invocation_executed)

    def test_invocation_hooks_app_level_should_be_executed(self):
        """If there is an extension implemented the pre_invocation and
        post_invocation life-cycle hooks, it should be invoked in
        safe_execute_invocation_hooks
        """
        AppExtClass = self._generate_new_app_extension(
            base=self._sdk.AppExtensionBase
        )
        hook_instances = (
            self._sdk.ExtensionMeta.get_application_hooks()
        )
        for hook_name in (APP_EXT_PRE_INVOCATION, APP_EXT_POST_INVOCATION):
            self._instance._safe_execute_invocation_hooks(
                hooks=hook_instances,
                hook_name=hook_name,
                ctx=self._mock_context,
                fargs=[],
                fret=None
            )
        self.assertFalse(AppExtClass._post_function_load_app_level_executed)
        self.assertTrue(AppExtClass._pre_invocation_app_level_executed)
        self.assertTrue(AppExtClass._post_invocation_app_level_executed)

    def test_post_function_load_app_level_hook_should_be_executed(self):
        """If there is an extension implemented the post_function_load
        life-cycle hook, it invokes in safe_execute_function_load_hooks
        """
        AppExtClass = self._generate_new_app_extension(
            base=self._sdk.AppExtensionBase
        )
        hook_instances = (
            self._sdk.ExtensionMeta.get_application_hooks()
        )
        for hook_name in (APP_EXT_POST_FUNCTION_LOAD,):
            self._instance._safe_execute_function_load_hooks(
                hooks=hook_instances,
                hook_name=hook_name,
                fname=self._mock_func_name,
                fdir=self._mock_func_dir
            )
        self.assertTrue(AppExtClass._post_function_load_app_level_executed)
        self.assertFalse(AppExtClass._pre_invocation_app_level_executed)
        self.assertFalse(AppExtClass._post_invocation_app_level_executed)

    def test_raw_invocation_wrapper(self):
        """This wrapper should automatically invoke all invocation extensions
        """
        # Instantiate extensions
        AppExtClass = self._generate_new_app_extension(
            base=self._sdk.AppExtensionBase
        )
        FuncExtClass = self._generate_new_func_extension_class(
            base=self._sdk.FuncExtensionBase,
            trigger=self._mock_func_name
        )
        func_ext_instance = FuncExtClass()

        # Invoke with wrapper
        self._instance._raw_invocation_wrapper(
            self._mock_context, self._mock_function_main, self._mock_arguments
        )

        # Assert: invocation hooks should be executed
        self.assertTrue(func_ext_instance._pre_invocation_executed)
        self.assertTrue(func_ext_instance._post_invocation_executed)
        self.assertTrue(AppExtClass._pre_invocation_app_level_executed)
        self.assertTrue(AppExtClass._post_invocation_app_level_executed)

        # Assert: arguments should be passed into the extension
        comparisons = (
            func_ext_instance._pre_invocation_executed_fargs,
            func_ext_instance._post_invocation_executed_fargs,
            AppExtClass._pre_invocation_app_level_executed_fargs,
            AppExtClass._post_invocation_app_level_executed_fargs
        )
        for current_argument in comparisons:
            self.assertEqual(current_argument, self._mock_arguments)

        # Assert: returns should be passed into the extension
        comparisons = (
            func_ext_instance._post_invocation_executed_fret,
            AppExtClass._post_invocation_app_level_executed_fret
        )
        for current_return in comparisons:
            self.assertEqual(current_return, 'request_ok')

    @patch('azure_functions_worker.extension.logger.error')
    def test_exception_handling_in_post_function_load_app_level(
        self,
        error_mock: Mock
    ):
        """When there's a chain breaks in the extension chain, it should not
        pause other executions. For post_function_load_app_level, becasue the
        logger is not fully initialized, the exception will be suppressed.
        """
        # Create an customized exception
        expt = Exception('Exception in post_function_load_app_level')

        # Register an application extension
        class BadAppExtension(self._sdk.AppExtensionBase):
            post_function_load_app_level_executed = False

            @classmethod
            def post_function_load_app_level(cls,
                                             function_name,
                                             function_directory,
                                             *args,
                                             **kwargs):
                cls.post_function_load_app_level_executed = True
                raise expt

        # Execute function with a broken extension
        hooks = self._sdk.ExtensionMeta.get_application_hooks()
        self._instance._safe_execute_function_load_hooks(
            hooks=hooks,
            hook_name=APP_EXT_POST_FUNCTION_LOAD,
            fname=self._mock_func_name,
            fdir=self._mock_func_dir
        )

        # Ensure the extension is executed, but the exception shouldn't surface
        self.assertTrue(BadAppExtension.post_function_load_app_level_executed)

        # Ensure errors are reported from system logger
        error_mock.assert_called_with(expt, exc_info=True)

    def test_exception_handling_in_pre_invocation_app_level(self):
        """When there's a chain breaks in the extension chain, it should not
        pause other executions, but report with a system logger, so that the
        error is accessible to customers and ours.
        """
        # Create an customized exception
        expt = Exception('Exception in pre_invocation_app_level')

        # Register an application extension
        class BadAppExtension(self._sdk.AppExtensionBase):
            @classmethod
            def pre_invocation_app_level(cls, logger, context, func_args,
                                         *args, **kwargs):
                raise expt

        # Create a mocked customer_function
        wrapped = self._instance.get_sync_invocation_wrapper(
            self._mock_context,
            self._mock_function_main
        )

        # Mock logger
        ext_logger = logging.getLogger(
            'azure_functions_worker.extension.BadAppExtension'
        )
        ext_logger_error_mock = Mock()
        ext_logger.error = ext_logger_error_mock

        # Invocation with arguments. This will throw an exception, but should
        # not break the execution chain.
        result = wrapped(self._mock_arguments)

        # Ensure the customer's function is executed
        self.assertEqual(result, 'request_ok')

        # Ensure the error is reported
        ext_logger_error_mock.assert_called_with(expt, exc_info=True)

    def test_get_sync_invocation_wrapper_no_extension(self):
        """The wrapper is using functools.partial() to expose the arguments
        for synchronous execution in dispatcher.
        """
        # Create a mocked customer_function
        wrapped = self._instance.get_sync_invocation_wrapper(
            self._mock_context,
            self._mock_function_main
        )

        # Invocation with arguments
        result = wrapped(self._mock_arguments)

        # Ensure the return value matches the function method
        self.assertEqual(result, 'request_ok')

    def test_get_sync_invocation_wrapper_with_func_extension(self):
        """The wrapper is using functools.partial() to expose the arguments.
        Ensure the func extension can be executed along with customer's funcs.
        """
        # Register a function extension
        FuncExtClass = self._generate_new_func_extension_class(
            self._sdk.FuncExtensionBase,
            self._mock_func_name
        )
        _func_ext_instance = FuncExtClass()

        # Create a mocked customer_function
        wrapped = self._instance.get_sync_invocation_wrapper(
            self._mock_context,
            self._mock_function_main
        )

        # Invocation via wrapper with arguments
        result = wrapped(self._mock_arguments)

        # Ensure the extension is executed
        self.assertTrue(_func_ext_instance._pre_invocation_executed)

        # Ensure the customer's function is executed
        self.assertEqual(result, 'request_ok')

    def test_get_sync_invocation_wrapper_disabled_with_flag(self):
        """The wrapper should still exist, customer's functions should still
        be executed, but not the extension
        """
        # Turn off feature flag
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'false'

        # Register a function extension
        FuncExtClass = self._generate_new_func_extension_class(
            self._sdk.FuncExtensionBase,
            self._mock_func_name
        )
        _func_ext_instance = FuncExtClass()

        # Create a mocked customer_function
        wrapped = self._instance.get_sync_invocation_wrapper(
            self._mock_context,
            self._mock_function_main
        )

        # Invocation via wrapper with arguments
        result = wrapped(self._mock_arguments)

        # The extension SHOULD NOT be executed, since the feature flag is off
        self.assertFalse(_func_ext_instance._pre_invocation_executed)

        # Ensure the customer's function is executed
        self.assertEqual(result, 'request_ok')

    def test_get_async_invocation_wrapper_no_extension(self):
        """The async wrapper will wrap an asynchronous function with a
        coroutine interface. When there is no extension, it should only invoke
        the customer's function.
        """
        # Create a mocked customer_function with async wrapper
        result = aio_compat.run(
            self._instance.get_async_invocation_wrapper(
                self._mock_context,
                self._mock_function_main_async,
                self._mock_arguments
            )
        )

        # Ensure the return value matches the function method
        self.assertEqual(result, 'request_ok')

    def test_get_async_invocation_wrapper_with_func_extension(self):
        """The async wrapper will wrap an asynchronous function with a
        coroutine interface. When there is registered extension, it should
        execute the extension as well.
        """
        # Register a function extension
        FuncExtClass = self._generate_new_func_extension_class(
            self._sdk.FuncExtensionBase,
            self._mock_func_name
        )
        _func_ext_instance = FuncExtClass()

        # Create a mocked customer_function with async wrapper
        result = aio_compat.run(
            self._instance.get_async_invocation_wrapper(
                self._mock_context,
                self._mock_function_main_async,
                self._mock_arguments
            )
        )

        # Ensure the extension is executed
        self.assertTrue(_func_ext_instance._pre_invocation_executed)

        # Ensure the customer's function is executed
        self.assertEqual(result, 'request_ok')

    def test_get_invocation_async_disabled_with_flag(self):
        """The async wrapper will only execute customer's function. This
        should not execute the extension.
        """
        # Turn off feature flag
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'false'

        # Register a function extension
        FuncExtClass = self._generate_new_func_extension_class(
            self._sdk.FuncExtensionBase,
            self._mock_func_name
        )
        _func_ext_instance = FuncExtClass()

        # Create a mocked customer_function with async wrapper
        result = aio_compat.run(
            self._instance.get_async_invocation_wrapper(
                self._mock_context,
                self._mock_function_main_async,
                self._mock_arguments
            )
        )

        # The extension SHOULD NOT be executed
        self.assertFalse(_func_ext_instance._pre_invocation_executed)

        # Ensure the customer's function is executed
        self.assertEqual(result, 'request_ok')

    def test_is_pre_invocation_hook(self):
        for name in (FUNC_EXT_PRE_INVOCATION, APP_EXT_PRE_INVOCATION):
            self.assertTrue(
                self._instance._is_pre_invocation_hook(name)
            )

    def test_is_pre_invocation_hook_negative(self):
        for name in (FUNC_EXT_POST_INVOCATION, APP_EXT_POST_INVOCATION,
                     FUNC_EXT_POST_FUNCTION_LOAD, APP_EXT_POST_FUNCTION_LOAD):
            self.assertFalse(
                self._instance._is_pre_invocation_hook(name)
            )

    def test_is_post_invocation_hook(self):
        for name in (FUNC_EXT_POST_INVOCATION, APP_EXT_POST_INVOCATION):
            self.assertTrue(
                self._instance._is_post_invocation_hook(name)
            )

    def test_is_post_invocation_hook_negative(self):
        for name in (FUNC_EXT_PRE_INVOCATION, APP_EXT_PRE_INVOCATION,
                     FUNC_EXT_POST_FUNCTION_LOAD, APP_EXT_POST_FUNCTION_LOAD):
            self.assertFalse(
                self._instance._is_post_invocation_hook(name)
            )

    @patch('azure_functions_worker.extension.'
           'ExtensionManager._info_extension_is_enabled')
    def test_try_get_sdk_with_extension_enabled_should_execute_once(
        self,
        info_extension_is_enabled_mock: Mock
    ):
        """The result of an extension enabled SDK should be cached. No need
        to be derived multiple times.
        """
        # Call twice the function
        self._instance._try_get_sdk_with_extension_enabled()
        sdk = self._instance._try_get_sdk_with_extension_enabled()

        # The actual execution will only process once (e.g. list extensions)
        info_extension_is_enabled_mock.assert_called_once()

        # Ensure the SDK is returned correctly
        self.assertIsNotNone(sdk)

    @patch('azure_functions_worker.extension.'
           'ExtensionManager._warn_sdk_not_support_extension')
    def test_try_get_sdk_with_extension_disabled_should_execute_once(
        self,
        warn_sdk_not_support_extension_mock: Mock
    ):
        """When SDK does not support extension interface, it should return
        None and throw a warning.
        """
        # Point to dummy SDK
        sys.path.insert(0, self._dummy_sdk_sys_path)

        # Call twice the function
        self._instance._try_get_sdk_with_extension_enabled()
        sdk = self._instance._try_get_sdk_with_extension_enabled()

        # The actual execution will only process once (e.g. warning)
        warn_sdk_not_support_extension_mock.assert_called_once()

        # The SDK does not support Extension Interface, should be None
        self.assertIsNone(sdk)

    @patch('azure_functions_worker.extension.logger.info')
    def test_info_extension_is_enabled(self, info_mock: Mock):
        # Get SDK from sys.path
        sdk = get_sdk_from_sys_path()

        # Check logs
        self._instance._info_extension_is_enabled(sdk)
        info_mock.assert_called_once_with(
            'Python Worker Extension is enabled in azure.functions '
            f'({sdk.__version__}).'
        )

    @patch('azure_functions_worker.extension.logger.info')
    def test_info_discover_extension_list_func_ext(self, info_mock: Mock):
        # Get SDK from sys.path
        sdk = get_sdk_from_sys_path()

        # Register a function extension class
        FuncExtClass = self._generate_new_func_extension_class(
            sdk.FuncExtensionBase,
            self._mock_func_name
        )

        # Instantiate a function extension
        FuncExtClass()

        # Check logs
        self._instance._info_discover_extension_list(self._mock_func_name, sdk)
        info_mock.assert_called_once_with(
            'Python Worker Extension Manager is loading HttpTrigger, '
            'current registered extensions: '
            r'{"FuncExtension": {"HttpTrigger": ["NewFuncExtension"]}}'
        )

    @patch('azure_functions_worker.extension.logger.info')
    def test_info_discover_extension_list_app_ext(self, info_mock: Mock):
        # Get SDK from sys.path
        sdk = get_sdk_from_sys_path()

        # Register a function extension class
        self._generate_new_app_extension(sdk.AppExtensionBase)

        # Check logs
        self._instance._info_discover_extension_list(self._mock_func_name, sdk)
        info_mock.assert_called_once_with(
            'Python Worker Extension Manager is loading HttpTrigger, '
            'current registered extensions: '
            r'{"AppExtension": ["NewAppExtension"]}'
        )

    @patch('azure_functions_worker.extension.logger.warning')
    def test_warn_sdk_not_support_extension(self, warning_mock: Mock):
        # Get SDK from dummy
        sys.path.insert(0, self._dummy_sdk_sys_path)
        sdk = get_sdk_from_sys_path()

        # Check logs
        self._instance._warn_sdk_not_support_extension(sdk)
        warning_mock.assert_called_once_with(
            'The azure.functions (dummy) does not '
            'support Python worker extensions. If you believe extensions '
            'are correctly installed, please set the '
            'PYTHON_ISOLATE_WORKER_DEPENDENCIES and '
            'PYTHON_ENABLE_WORKER_EXTENSIONS to "true"'
        )

    def _generate_new_func_extension_class(self, base: type, trigger: str):
        class NewFuncExtension(base):
            def __init__(self):
                self._trigger_name = trigger
                self._post_function_load_executed = False
                self._pre_invocation_executed = False
                self._post_invocation_executed = False

                self._pre_invocation_executed_fargs = {}
                self._post_invocation_executed_fargs = {}
                self._post_invocation_executed_fret = None

            def post_function_load(self,
                                   function_name,
                                   function_directory,
                                   *args,
                                   **kwargs):
                self._post_function_load_executed = True

            def pre_invocation(self, logger, context, fargs,
                               *args, **kwargs):
                self._pre_invocation_executed = True
                self._pre_invocation_executed_fargs = fargs

            def post_invocation(self, logger, context, fargs, fret,
                                *args, **kwargs):
                self._post_invocation_executed = True
                self._post_invocation_executed_fargs = fargs
                self._post_invocation_executed_fret = fret

        return NewFuncExtension

    def _generate_new_app_extension(self, base: type):
        class NewAppExtension(base):
            _init_executed = False

            _post_function_load_app_level_executed = False
            _pre_invocation_app_level_executed = False
            _post_invocation_app_level_executed = False

            _pre_invocation_app_level_executed_fargs = {}
            _post_invocation_app_level_executed_fargs = {}
            _post_invocation_app_level_executed_fret = None

            @classmethod
            def init(cls):
                cls._init_executed = True

            @classmethod
            def post_function_load_app_level(cls,
                                             function_name,
                                             function_directory,
                                             *args,
                                             **kwargs):
                cls._post_function_load_app_level_executed = True

            @classmethod
            def pre_invocation_app_level(cls, logger, context, func_args,
                                         *args, **kwargs):
                cls._pre_invocation_app_level_executed = True
                cls._pre_invocation_app_level_executed_fargs = func_args

            @classmethod
            def post_invocation_app_level(cls, logger, context,
                                          func_args, func_ret,
                                          *args, **kwargs):
                cls._post_invocation_app_level_executed = True
                cls._post_invocation_app_level_executed_fargs = func_args
                cls._post_invocation_app_level_executed_fret = func_ret

        return NewAppExtension

    def _mock_function_main(self, req):
        assert req == 'request'
        return req + '_ok'

    async def _mock_function_main_async(self, req):
        assert req == 'request'
        return req + '_ok'
