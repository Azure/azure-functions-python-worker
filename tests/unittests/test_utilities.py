# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import unittest
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

    @wrappers.disable_feature_by(TEST_FEATURE_FLAG)
    def mock_feature_disabled(self, output: typing.List[str]) -> str:
        result = 'mock_feature_disabled'
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
        self._pre_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._pre_env)

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

    def test_is_envvar_true(self):
        os.environ[TEST_FEATURE_FLAG] = 'true'
        self.assertTrue(common.is_envvar_true(TEST_FEATURE_FLAG))

    def test_is_envvar_not_true_on_unset(self):
        self._unset_feature_flag()
        self.assertFalse(common.is_envvar_true(TEST_FEATURE_FLAG))

    def test_disable_feature_with_no_feature_flag(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_enabled(output)
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

    def test_enable_feature_with_no_rollback_flag(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_disabled(output)
        self.assertEqual(result, 'mock_feature_disabled')
        self.assertListEqual(output, ['mock_feature_disabled'])

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

    def _unset_feature_flag(self):
        try:
            os.environ.pop(TEST_FEATURE_FLAG)
        except KeyError:
            pass
