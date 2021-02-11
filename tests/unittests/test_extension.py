# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import sys
import unittest
from uuid import uuid4
from unittest.mock import MagicMock, patch, Mock
from azure_functions_worker import extension
from azure_functions_worker.constants import (
    PYTHON_ENABLE_WORKER_EXTENSIONS,
    PYTHON_ISOLATE_WORKER_DEPENDENCIES
)


class TestExtension(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.mock_sdk_with_ext_path = os.path.join(
            os.path.dirname(__file__), 'resources', 'mock_sdk_with_ext'
        )
        cls.mock_sdk_without_ext_path = os.path.join(
            os.path.dirname(__file__), 'resources', 'mock_sdk_without_ext'
        )

        if sys.modules.get('azure.functions'):
            sys.modules.pop('azure')
            sys.modules.pop('azure.functions')

    def setUp(self):
        super().setUp()

        self.mock_sys_module = patch.dict('sys.modules', sys.modules.copy())
        self.mock_sys_path = patch('sys.path', sys.path.copy())

        self.mock_sys_module.start()
        self.mock_sys_path.start()
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'true'

    def tearDown(self) -> None:
        super().tearDown()
        self.mock_sys_path.stop()
        self.mock_sys_module.stop()
        del os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS]

    def test_extension_get_sdk_from_sys_path(self):
        """Test if the get_sdk_from_sys_path can find azure.functions module
        """
        module = extension.get_sdk_from_sys_path()
        self.assertIsNotNone(module.__file__)

    def test_extension_get_sdk_from_sys_path_after_updating_sys_path(self):
        """Test if the get_sdk_from_sys_path can find the newer azure.functions
        module after updating the sys.path. This is specifically for a scenario
        after the dependency manager is switched to customer's path
        """
        sys.path.insert(0, TestExtension.mock_sdk_with_ext_path)
        module = extension.get_sdk_from_sys_path()
        self.assertEqual(
            os.path.dirname(module.__file__),
            os.path.join(TestExtension.mock_sdk_with_ext_path,
                         'azure', 'functions')
        )

    def test_extension_get_sdk_from_sys_path_without_updating_sys_path(self):
        """Test if the get_sdk_from_sys_path can find the original worker's
        azure.functions module without updating the sys.path. This is for
        testing if the function works in placeholder mode (Linux Consumption)
        """
        module = extension.get_sdk_from_sys_path()
        self.assertNotEqual(
            os.path.dirname(module.__file__),
            os.path.join(TestExtension.mock_sdk_with_ext_path,
                         'azure', 'functions')
        )  # Indicating the package is not loaded from original path

    def test_is_extension_supported_has_sdk(self):
        """Test if the new sdk supports extension
        """
        sys.path.insert(0, TestExtension.mock_sdk_with_ext_path)
        module = extension.get_sdk_from_sys_path()
        supports_ext = extension.is_extension_enabled_in_sdk(module)
        self.assertTrue(supports_ext)

    def test_is_extension_supported_without_sdk(self):
        """Test if the old sdk does not support extension
        """
        sys.path.insert(0, TestExtension.mock_sdk_without_ext_path)
        module = extension.get_sdk_from_sys_path()
        supports_ext = extension.is_extension_enabled_in_sdk(module)
        self.assertFalse(supports_ext)

    def test_get_sdk_version(self):
        """Test if the sdk version is defined"""
        sys.path.insert(0, TestExtension.mock_sdk_with_ext_path)
        module = extension.get_sdk_from_sys_path()
        sdk_version = extension.get_sdk_version(module)
        self.assertEqual(sdk_version, '1.7.0')

    def test_get_sdk_version_undefined(self):
        """Test if the sdk version is undefined"""
        sys.path.insert(0, TestExtension.mock_sdk_without_ext_path)
        module = extension.get_sdk_from_sys_path()
        sdk_version = extension.get_sdk_version(module)
        self.assertEqual(sdk_version, 'undefined')

    def test_get_sdk_version_worker_azure_functions(self):
        """Check azure.functions package in worker should have version"""
        module = extension.get_sdk_from_sys_path()
        sdk_version = extension.get_sdk_version(module)
        self.assertNotEqual(sdk_version, 'undefined')

    def test_mock_invoke_before_invocations(self):
        """Check if invocation can be sucessfully executed"""
        sys.path.insert(0, TestExtension.mock_sdk_with_ext_path)

        context = MagicMock()
        context.function_name = 'HttpTrigger'
        extension.invoke_extension(context, 'before_invocation')

        from azure.functions import MockExtension
        self.assertEqual(
            MockExtension.before_invocation_context.function_name,
            context.function_name
        )

    def test_invoke_before_invocations_disabled_by_feature_flag(self):
        """Check if invocation can be disabled by feature flag"""
        os.environ[PYTHON_ENABLE_WORKER_EXTENSIONS] = 'false'
        sys.path.insert(0, TestExtension.mock_sdk_with_ext_path)

        context = MagicMock()
        context.function_name = 'HttpTrigger'
        extension.invoke_extension(context, 'before_invocation')

        from azure.functions import MockExtension
        self.assertIsNone(MockExtension.before_invocation_context)

    @patch('azure_functions_worker.extension.logger')
    def test_invoke_before_invocations_sdk_not_supported(self,
                                                         logger: MagicMock):
        """Check if a warning message will be thrown if sdk does not support
        extension
        """
        sys.path.insert(0, TestExtension.mock_sdk_without_ext_path)

        context = str(uuid4())
        extension.invoke_extension(context, 'before_invocation')

        logger.warning.assert_called_once_with(
            'The azure.functions (undefined) does not '
            'support Python worker extensions. If you believe '
            'extensions are correctly installed, please set the '
            f'{PYTHON_ISOLATE_WORKER_DEPENDENCIES} and '
            f'{PYTHON_ENABLE_WORKER_EXTENSIONS} to "true"'
        )

    def test_raw_invocation_wrapper(self):
        """As _after_invocation is missing. It only executes _before_invocation
        """
        sys.path.insert(0, TestExtension.mock_sdk_with_ext_path)

        # Setup mock function
        context = MagicMock()
        context.function_name = 'HttpTrigger'
        expected_result = str(uuid4())
        function = Mock(return_value=expected_result)
        result = extension.raw_invocation_wrapper(
            context, function, {'ok': 1}
        )

        # Check if function is executed
        function.assert_called_once_with(ok=1)
        self.assertEqual(result, expected_result)
