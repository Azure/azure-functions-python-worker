# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
import unittest
from unittest.mock import patch
import typing

from azure_functions_worker.utils import common, wrappers


TEST_APP_SETTING_NAME = "TEST_APP_SETTING_NAME"
TEST_FEATURE_FLAG = "APP_SETTING_FEATURE_FLAG"
FEATURE_DEFAULT = 42


class MockFeature:
    @wrappers.enable_feature_by(TEST_FEATURE_FLAG)
    def mock_feature_enabled(self, output: typing.List[str]) -> str:
        result = 'mock_feature_enabled'
        output.append(result)
        return result

    @wrappers.enable_feature_by(TEST_FEATURE_FLAG, flag_default=True)
    def mock_enabled_default_true(self, output: typing.List[str]) -> str:
        result = 'mock_enabled_default_true'
        output.append(result)
        return result

    @wrappers.disable_feature_by(TEST_FEATURE_FLAG)
    def mock_feature_disabled(self, output: typing.List[str]) -> str:
        result = 'mock_feature_disabled'
        output.append(result)
        return result

    @wrappers.disable_feature_by(TEST_FEATURE_FLAG, flag_default=True)
    def mock_disabled_default_true(self, output: typing.List[str]) -> str:
        result = 'mock_disabled_default_true'
        output.append(result)
        return result

    @wrappers.enable_feature_by(TEST_FEATURE_FLAG, FEATURE_DEFAULT)
    def mock_feature_default(self, output: typing.List[str]) -> str:
        result = 'mock_feature_default'
        output.append(result)
        return result


class MockMethod:
    @wrappers.attach_message_to_exception(ImportError, 'success')
    def mock_load_function_success(self):
        return True

    @wrappers.attach_message_to_exception(ImportError, 'module_not_found')
    def mock_load_function_module_not_found(self):
        raise ModuleNotFoundError('MODULE_NOT_FOUND')

    @wrappers.attach_message_to_exception(ImportError, 'import_error')
    def mock_load_function_import_error(self):
        # ImportError is a subclass of ModuleNotFoundError
        raise ImportError('IMPORT_ERROR')

    @wrappers.attach_message_to_exception(ImportError, 'value_error')
    def mock_load_function_value_error(self):
        # ValueError is not a subclass of ImportError
        raise ValueError('VALUE_ERROR')


class TestUtilities(unittest.TestCase):

    def setUp(self):
        self._dummy_sdk_sys_path = os.path.join(
            os.path.dirname(__file__),
            'resources',
            'mock_azure_functions'
        )

        self.mock_environ = patch.dict('os.environ', os.environ.copy())
        self.mock_sys_module = patch.dict('sys.modules', sys.modules.copy())
        self.mock_sys_path = patch('sys.path', sys.path.copy())
        self.mock_environ.start()
        self.mock_sys_module.start()
        self.mock_sys_path.start()

    def tearDown(self):
        self.mock_sys_path.stop()
        self.mock_sys_module.stop()
        self.mock_environ.stop()

    def test_is_true_like_accepted(self):
        self.assertTrue(common.is_true_like('1'))
        self.assertTrue(common.is_true_like('true'))
        self.assertTrue(common.is_true_like('T'))
        self.assertTrue(common.is_true_like('YES'))
        self.assertTrue(common.is_true_like('y'))

    def test_is_true_like_rejected(self):
        self.assertFalse(common.is_true_like(None))
        self.assertFalse(common.is_true_like(''))
        self.assertFalse(common.is_true_like('secret'))

    def test_is_false_like_accepted(self):
        self.assertTrue(common.is_false_like('0'))
        self.assertTrue(common.is_false_like('false'))
        self.assertTrue(common.is_false_like('F'))
        self.assertTrue(common.is_false_like('NO'))
        self.assertTrue(common.is_false_like('n'))

    def test_is_false_like_rejected(self):
        self.assertFalse(common.is_false_like(None))
        self.assertFalse(common.is_false_like(''))
        self.assertFalse(common.is_false_like('secret'))

    def test_is_envvar_true(self):
        os.environ[TEST_FEATURE_FLAG] = 'true'
        self.assertTrue(common.is_envvar_true(TEST_FEATURE_FLAG))

    def test_is_envvar_not_true_on_unset(self):
        self._unset_feature_flag()
        self.assertFalse(common.is_envvar_true(TEST_FEATURE_FLAG))

    def test_is_envvar_false(self):
        os.environ[TEST_FEATURE_FLAG] = 'false'
        self.assertTrue(common.is_envvar_false(TEST_FEATURE_FLAG))

    def test_is_envvar_not_false_on_unset(self):
        self._unset_feature_flag()
        self.assertFalse(common.is_envvar_true(TEST_FEATURE_FLAG))

    def test_disable_feature_with_no_feature_flag(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_enabled(output)
        self.assertIsNone(result)
        self.assertListEqual(output, [])

    def test_disable_feature_with_default_value(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_disabled_default_true(output)
        self.assertIsNone(result)
        self.assertListEqual(output, [])

    def test_enable_feature_with_feature_flag(self):
        feature_flag = TEST_FEATURE_FLAG
        os.environ[feature_flag] = '1'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_enabled(output)
        self.assertEqual(result, 'mock_feature_enabled')
        self.assertListEqual(output, ['mock_feature_enabled'])

    def test_enable_feature_with_default_value(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_enabled_default_true(output)
        self.assertEqual(result, 'mock_enabled_default_true')
        self.assertListEqual(output, ['mock_enabled_default_true'])

    def test_enable_feature_with_no_rollback_flag(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_disabled(output)
        self.assertEqual(result, 'mock_feature_disabled')
        self.assertListEqual(output, ['mock_feature_disabled'])

    def test_ignore_disable_default_value_when_set_explicitly(self):
        feature_flag = TEST_FEATURE_FLAG
        os.environ[feature_flag] = '0'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_disabled_default_true(output)
        self.assertEqual(result, 'mock_disabled_default_true')
        self.assertListEqual(output, ['mock_disabled_default_true'])

    def test_disable_feature_with_rollback_flag(self):
        rollback_flag = TEST_FEATURE_FLAG
        os.environ[rollback_flag] = '1'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_disabled(output)
        self.assertIsNone(result)
        self.assertListEqual(output, [])

    def test_enable_feature_with_rollback_flag_is_false(self):
        rollback_flag = TEST_FEATURE_FLAG
        os.environ[rollback_flag] = 'false'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_disabled(output)
        self.assertEqual(result, 'mock_feature_disabled')
        self.assertListEqual(output, ['mock_feature_disabled'])

    def test_ignore_enable_default_value_when_set_explicitly(self):
        feature_flag = TEST_FEATURE_FLAG
        os.environ[feature_flag] = '0'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_enabled_default_true(output)
        self.assertIsNone(result)
        self.assertListEqual(output, [])

    def test_fail_to_enable_feature_return_default_value(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_default(output)
        self.assertEqual(result, FEATURE_DEFAULT)
        self.assertListEqual(output, [])

    def test_disable_feature_with_false_flag_return_default_value(self):
        feature_flag = TEST_FEATURE_FLAG
        os.environ[feature_flag] = 'false'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_default(output)
        self.assertEqual(result, FEATURE_DEFAULT)
        self.assertListEqual(output, [])

    def test_exception_message_should_not_be_extended_on_success(self):
        mock_method = MockMethod()
        result = mock_method.mock_load_function_success()
        self.assertTrue(result)

    def test_exception_message_should_be_extended_on_subexception(self):
        mock_method = MockMethod()
        with self.assertRaises(Exception) as e:
            mock_method.mock_load_function_module_not_found()
            self.assertIn('module_not_found', e.msg)
            self.assertEqual(type(e), ModuleNotFoundError)

    def test_exception_message_should_be_extended_on_exact_exception(self):
        mock_method = MockMethod()
        with self.assertRaises(Exception) as e:
            mock_method.mock_load_function_module_not_found()
            self.assertIn('import_error', e.msg)
            self.assertEqual(type(e), ImportError)

    def test_exception_message_should_not_be_extended_on_other_exception(self):
        mock_method = MockMethod()
        with self.assertRaises(Exception) as e:
            mock_method.mock_load_function_value_error()
            self.assertNotIn('import_error', e.msg)
            self.assertEqual(type(e), ValueError)

    def test_app_settings_not_set_should_return_none(self):
        app_setting = common.get_app_setting(TEST_APP_SETTING_NAME)
        self.assertIsNone(app_setting)

    def test_app_settings_should_return_value(self):
        # Set application setting by os.setenv
        os.environ.update({TEST_APP_SETTING_NAME: '42'})

        # Try using utility to acquire application setting
        app_setting = common.get_app_setting(TEST_APP_SETTING_NAME)
        self.assertEqual(app_setting, '42')

    def test_app_settings_not_set_should_return_default_value(self):
        app_setting = common.get_app_setting(TEST_APP_SETTING_NAME, 'default')
        self.assertEqual(app_setting, 'default')

    def test_app_settings_should_ignore_default_value(self):
        # Set application setting by os.setenv
        os.environ.update({TEST_APP_SETTING_NAME: '42'})

        # Try using utility to acquire application setting
        app_setting = common.get_app_setting(TEST_APP_SETTING_NAME, 'default')
        self.assertEqual(app_setting, '42')

    def test_app_settings_should_not_trigger_validator_when_not_set(self):
        def raise_excpt(value: str):
            raise Exception('Should not raise on app setting not found')

        common.get_app_setting(TEST_APP_SETTING_NAME, validator=raise_excpt)

    def test_app_settings_return_default_value_when_validation_fail(self):
        def parse_int_no_raise(value: str):
            try:
                int(value)
                return True
            except ValueError:
                return False

        # Set application setting to an invalid value
        os.environ.update({TEST_APP_SETTING_NAME: 'invalid'})

        app_setting = common.get_app_setting(
            TEST_APP_SETTING_NAME,
            default_value='1',
            validator=parse_int_no_raise
        )

        # Because 'invalid' is not an interger, falls back to default value
        self.assertEqual(app_setting, '1')

    def test_app_settings_return_setting_value_when_validation_succeed(self):
        def parse_int_no_raise(value: str):
            try:
                int(value)
                return True
            except ValueError:
                return False

        # Set application setting to an invalid value
        os.environ.update({TEST_APP_SETTING_NAME: '42'})

        app_setting = common.get_app_setting(
            TEST_APP_SETTING_NAME,
            default_value='1',
            validator=parse_int_no_raise
        )

        # Because 'invalid' is not an interger, falls back to default value
        self.assertEqual(app_setting, '42')

    def test_is_python_version(self):
        # Should pass at least 1 test
        is_python_version_36 = common.is_python_version('3.6')
        is_python_version_37 = common.is_python_version('3.7')
        is_python_version_38 = common.is_python_version('3.8')
        is_python_version_39 = common.is_python_version('3.9')

        self.assertTrue(any([
            is_python_version_36,
            is_python_version_37,
            is_python_version_38,
            is_python_version_39
        ]))

    def test_get_sdk_from_sys_path(self):
        """Test if the extension manager can find azure.functions module
        """
        module = common.get_sdk_from_sys_path()
        self.assertIsNotNone(module.__file__)

    def test_get_sdk_from_sys_path_after_updating_sys_path(self):
        """Test if the get_sdk_from_sys_path can find the newer azure.functions
        module after updating the sys.path. This is specifically for a scenario
        after the dependency manager is switched to customer's path
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        module = common.get_sdk_from_sys_path()
        self.assertEqual(
            os.path.dirname(module.__file__),
            os.path.join(self._dummy_sdk_sys_path, 'azure', 'functions')
        )

    def test_get_sdk_version(self):
        """Test if sdk version can be retrieved correctly
        """
        module = common.get_sdk_from_sys_path()
        sdk_version = common.get_sdk_version(module)
        # e.g. 1.6.0, 1.7.0b, 1.8.1dev
        self.assertRegex(sdk_version, r'\d+\.\d+\.\w+')

    def test_get_sdk_dummy_version(self):
        """Test if sdk version can get dummy sdk version
        """
        sys.path.insert(0, self._dummy_sdk_sys_path)
        module = common.get_sdk_from_sys_path()
        sdk_version = common.get_sdk_version(module)
        self.assertEqual(sdk_version, 'dummy')

    def _unset_feature_flag(self):
        try:
            os.environ.pop(TEST_FEATURE_FLAG)
        except KeyError:
            pass
