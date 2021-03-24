# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import sys
import unittest
from unittest.mock import patch, Mock, call
from importlib import import_module
from azure_functions_worker.extension import ExtensionManager
from azure_functions_worker.constants import (
    PYTHON_ENABLE_WORKER_EXTENSIONS,
    APP_EXT_POST_FUNCTION_LOAD, FUNC_EXT_POST_FUNCTION_LOAD,
    APP_EXT_PRE_INVOCATION, FUNC_EXT_PRE_INVOCATION,
    APP_EXT_POST_INVOCATION, FUNC_EXT_POST_INVOCATION
)


class MockContext:
    def __init__(self, function_name: str, function_directory: str):
        self.function_name = function_name
        self.function_directory = function_directory


class TestExtension(unittest.TestCase):

    def setUp(self):
        # Initialize Extension Manager Instance
        self._instance = ExtensionManager
        self._instance.is_sdk_detected = False
        self._instance.extension_enabled_sdk = None

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
        self._mock_func_name = 'HttpTrigger'
        self._mock_func_dir = '/home/site/wwwroot/HttpTrigger'
        self._mock_context = MockContext(
            function_name=self._mock_func_name,
            function_directory=self._mock_func_dir
        )

        # Patch sys.modules and sys.path to avoid pollution between tests
        self.mock_sys_module = patch.dict('sys.modules', sys.modules.copy())
        self.mock_sys_path = patch('sys.path', sys.path.copy())
        self.mock_sys_module.start()
        self.mock_sys_path.start()

        # Set feature flag to on
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'true'

    def tearDown(self) -> None:
        self.mock_sys_path.stop()
        self.mock_sys_module.stop()
        os.environ.pop(PYTHON_ENABLE_WORKER_EXTENSIONS)

    def test_extension_get_sdk_from_sys_path(self):
        """Test if the extension manager can find azure.functions module
        """
        module = self._instance.get_sdk_from_sys_path()
        self.assertIsNotNone(module.__file__)

    def test_extension_get_sdk_from_sys_path_after_updating_sys_path(self):
        """Test if the get_sdk_from_sys_path can find the newer azure.functions
        module after updating the sys.path. This is specifically for a scenario
        after the dependency manager is switched to customer's path
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        module = self._instance.get_sdk_from_sys_path()
        self.assertEqual(
            os.path.dirname(module.__file__),
            os.path.join(self._dummy_sdk_sys_path, 'azure', 'functions')
        )

    def test_extension_is_supported_by_latest_sdk(self):
        """Test if extension interface supports check as expected on
        new version of azure.functions SDK
        """
        module = self._instance.get_sdk_from_sys_path()
        sdk_enabled = self._instance.is_extension_enabled_in_sdk(module)
        self.assertTrue(sdk_enabled)

    def test_extension_is_not_supported_by_mock_sdk(self):
        """Test if the detection works when an azure.functions SDK does not
        support extension management.
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        module = self._instance.get_sdk_from_sys_path()
        sdk_enabled = self._instance.is_extension_enabled_in_sdk(module)
        self.assertFalse(sdk_enabled)

    def test_get_sdk_version(self):
        """Test if sdk version can be retrieved correctly
        """
        module = self._instance.get_sdk_from_sys_path()
        sdk_version = self._instance.get_sdk_version(module)
        # e.g. 1.6.0, 1.7.0b, 1.8.1dev
        self.assertRegex(sdk_version, r'\d+\.\d+\.\w+')

    def test_get_sdk_dummy_version(self):
        """Test if sdk version can get dummy sdk version
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        module = self._instance.get_sdk_from_sys_path()
        sdk_version = self._instance.get_sdk_version(module)
        self.assertEqual(sdk_version, 'dummy')

    @patch('azure_functions_worker.extension.'
           'ExtensionManager.get_sdk_from_sys_path')
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

    @patch('azure_functions_worker.extension.ExtensionManager.'
           'get_sdk_from_sys_path')
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
           '_warn_extension_is_not_enabled_in_sdk')
    def test_function_load_extension_warns_when_sdk_does_not_support(
        self,
        _warn_extension_is_not_enabled_in_sdk_mock: Mock
    ):
        """When customer is using an old version of sdk which does not have
        extension support and turning on the feature flag, we should warn them
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        self._instance.function_load_extension(
            func_name=self._mock_func_name,
            func_directory=self._mock_func_dir
        )
        _warn_extension_is_not_enabled_in_sdk_mock.assert_called_once()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           'safe_execute_function_load_hooks')
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

    @patch('azure_functions_worker.extension.'
           'ExtensionManager.get_sdk_from_sys_path')
    def test_invocation_extension_enable_when_feature_flag_is_on(
        self,
        get_sdk_from_sys_path_mock: Mock
    ):
        """When turning off the feature flag PYTHON_ENABLE_WORKER_EXTENSIONS,
        the pre_invocation and post_invocation extension should be disabled
        """
        self._instance.invocation_extension(
            ctx=self._mock_context,
            hook_name=FUNC_EXT_PRE_INVOCATION,
            func_args=[],
            func_ret=None
        )
        get_sdk_from_sys_path_mock.assert_called_once()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           'get_sdk_from_sys_path')
    def test_invocation_extension_extension_disable_when_feature_flag_is_off(
        self,
        get_sdk_from_sys_path_mock: Mock
    ):
        """When turning off the feature flag PYTHON_ENABLE_WORKER_EXTENSIONS,
        the pre_invocation and post_invocation extension should be disabled
        """
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'false'
        self._instance.invocation_extension(
            ctx=self._mock_context,
            hook_name=FUNC_EXT_PRE_INVOCATION,
            func_args=[],
            func_ret=None
        )
        get_sdk_from_sys_path_mock.assert_not_called()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           '_warn_extension_is_not_enabled_in_sdk')
    def test_invocation_extension_warns_when_sdk_does_not_support(
        self,
        _warn_extension_is_not_enabled_in_sdk_mock: Mock
    ):
        """When customer is using an old version of sdk which does not have
        extension support and turning on the feature flag, we should warn them
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        self._instance.invocation_extension(
            ctx=self._mock_context,
            hook_name=FUNC_EXT_PRE_INVOCATION,
            func_args=[],
            func_ret=None
        )
        _warn_extension_is_not_enabled_in_sdk_mock.assert_called_once()

    @patch('azure_functions_worker.extension.ExtensionManager.'
           'safe_execute_invocation_hooks')
    def test_invocation_extension_should_invoke_extension_call(
        self,
        safe_execute_invocation_hooks_mock: Mock
    ):
        """Should invoke extension if SDK suports extension interface
        """
        for hook_name in (APP_EXT_PRE_INVOCATION, FUNC_EXT_PRE_INVOCATION,
                          APP_EXT_POST_INVOCATION, FUNC_EXT_POST_INVOCATION):
            self._instance.invocation_extension(
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
            self._instance.safe_execute_invocation_hooks(
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
            self._instance.safe_execute_invocation_hooks(
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
            self._instance.safe_execute_function_load_hooks(
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
            self._instance.safe_execute_invocation_hooks(
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
            self._instance.safe_execute_function_load_hooks(
                hooks=hook_instances,
                hook_name=hook_name,
                fname=self._mock_func_name,
                fdir=self._mock_func_dir
            )
        self.assertTrue(AppExtClass._post_function_load_app_level_executed)
        self.assertFalse(AppExtClass._pre_invocation_app_level_executed)
        self.assertFalse(AppExtClass._post_invocation_app_level_executed)

    def _generate_new_func_extension_class(self, base: type, trigger: str):
        class NewFuncExtension(base):
            def __init__(self):
                self._trigger_name = trigger
                self._post_function_load_executed = False
                self._pre_invocation_executed = False
                self._post_invocation_executed = False

            def post_function_load(self,
                                   function_name,
                                   function_directory,
                                   *args,
                                   **kwargs):
                self._post_function_load_executed = True

            def pre_invocation(self, logger, context, fargs,
                               *args, **kwargs):
                self._pre_invocation_executed = True

            def post_invocation(self, logger, context, fargs, fret,
                                *args, **kwargs):
                self._post_invocation_executed = True

        return NewFuncExtension

    def _generate_new_app_extension(self, base: type):
        class NewAppExtension(base):
            _init_executed = False
            _post_function_load_app_level_executed = False
            _pre_invocation_app_level_executed = False
            _post_invocation_app_level_executed = False

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
            def pre_invocation_app_level(cls, logger, context,
                                         *args, **kwargs):
                cls._pre_invocation_app_level_executed = True

            @classmethod
            def post_invocation_app_level(cls, logger, context,
                                          *args, **kwargs):
                cls._post_invocation_app_level_executed = True

        return NewAppExtension
