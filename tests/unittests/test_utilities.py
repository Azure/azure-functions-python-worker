import os
import unittest
import typing

from azure_functions_worker.utils import common, wrappers


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

    def _unset_feature_flag(self):
        try:
            os.environ.pop(TEST_FEATURE_FLAG)
        except KeyError:
            pass
