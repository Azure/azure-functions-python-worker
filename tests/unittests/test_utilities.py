import os
import unittest
import typing

from azure_functions_worker.utils import common, wrappers


class MockFeature:
    @wrappers.enable_feature_by("APP_SETTING_FEATURE_FLAG")
    def mock_feature_enabled(self, output: typing.List[str]) -> str:
        result = 'mock_feature_enabled'
        output.append(result)
        return result

    @wrappers.disable_feature_by("APP_SETTING_FEATURE_FLAG")
    def mock_feature_disabled(self, output: typing.List[str]) -> str:
        result = 'mock_feature_disabled'
        output.append(result)
        return result


class TestUtilities(unittest.TestCase):
    test_feature_flag = "APP_SETTING_FEATURE_FLAG"

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
        os.environ[self.test_feature_flag] = 'true'
        self.assertTrue(common.is_envvar_true(self.test_feature_flag))

    def test_is_envvar_false(self):
        os.environ[self.test_feature_flag] = 'false'
        self.assertTrue(common.is_envvar_false(self.test_feature_flag))

    def test_is_envvar_not_true_on_unset(self):
        self._unset_feature_flag()
        self.assertFalse(common.is_envvar_true(self.test_feature_flag))

    def test_is_envvar_not_false_on_unset(self):
        self._unset_feature_flag()
        self.assertFalse(common.is_envvar_false(self.test_feature_flag))

    def test_disable_feature_with_no_feature_flag(self):
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_enabled(output)
        self.assertIsNone(result)
        self.assertListEqual(output, [])

    def test_enable_feature_with_feature_flag(self):
        os.environ[self.test_feature_flag] = '1'
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
        self.rollback_flag = self.test_feature_flag
        os.environ[self.rollback_flag] = '1'
        mock_feature = MockFeature()
        output = []
        result = mock_feature.mock_feature_disabled(output)
        self.assertIsNone(result)
        self.assertListEqual(output, [])

    def _unset_feature_flag(self):
        try:
            os.environ.pop(self.test_feature_flag)
        except KeyError:
            pass
