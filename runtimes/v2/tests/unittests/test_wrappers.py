# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import unittest
from unittest.mock import patch, Mock

from azure_functions_runtime.utils import wrappers


class TestEnableFeatureBy(unittest.TestCase):

    @patch("wrappers.is_envvar_true", return_value=True)
    def test_enable_feature_by_flag_true(self, mock_true):
        func = Mock(return_value="enabled")
        decorated = wrappers.enable_feature_by("FLAG")(func)
        result = decorated()
        self.assertEqual(result, "enabled")
        func.assert_called_once()

    @patch("wrappers.is_envvar_true", return_value=False)
    @patch("wrappers.is_envvar_false", return_value=True)
    def test_enable_feature_by_flag_false(self, mock_false, mock_true):
        func = Mock(return_value="enabled")
        decorated = wrappers.enable_feature_by("FLAG", default="default")(func)
        result = decorated()
        self.assertEqual(result, "default")
        func.assert_not_called()

    @patch("wrappers.is_envvar_true", return_value=False)
    @patch("wrappers.is_envvar_false", return_value=False)
    def test_enable_feature_by_flag_default_true(self, mock_false, mock_true):
        func = Mock(return_value="enabled")
        decorated = wrappers.enable_feature_by("FLAG",
                                               default="default",
                                               flag_default=True)(func)
        result = decorated()
        self.assertEqual(result, "enabled")
        func.assert_called_once()


class TestDisableFeatureBy(unittest.TestCase):

    @patch("wrappers.is_envvar_true", return_value=True)
    def test_disable_feature_by_flag_true(self, mock_true):
        func = Mock(return_value="should_not_run")
        decorated = wrappers.disable_feature_by("FLAG", default="default")(func)
        result = decorated()
        self.assertEqual(result, "default")
        func.assert_not_called()

    @patch("wrappers.is_envvar_true", return_value=False)
    @patch("wrappers.is_envvar_false", return_value=True)
    def test_disable_feature_by_flag_false(self, mock_false, mock_true):
        func = Mock(return_value="enabled")
        decorated = wrappers.disable_feature_by("FLAG", default="default")(func)
        result = decorated()
        self.assertEqual(result, "enabled")
        func.assert_called_once()

    @patch("wrappers.is_envvar_true", return_value=False)
    @patch("wrappers.is_envvar_false", return_value=False)
    def test_disable_feature_by_flag_default_true(self, mock_false, mock_true):
        func = Mock(return_value="enabled")
        decorated = wrappers.disable_feature_by("FLAG",
                                                default="default",
                                                flag_default=True)(func)
        result = decorated()
        self.assertEqual(result, "default")
        func.assert_not_called()


class TestAttachMessageToException(unittest.TestCase):

    @patch("wrappers.logger")
    @patch("wrappers.extend_exception_message")
    def test_attach_message_to_exception_catches_and_logs(
            self, mock_extend, mock_logger):
        mock_extend.side_effect = lambda e, msg: Exception(f"{e} {msg}")

        def faulty_func():
            raise ValueError("original error")

        decorated = wrappers.attach_message_to_exception(
            ValueError, "extra info")(faulty_func)

        with self.assertRaises(Exception) as cm:
            decorated()

        self.assertIn("extra info", str(cm.exception))
        mock_logger.exception.assert_called_once()
        mock_extend.assert_called_once()

    @patch("wrappers.logger")
    @patch("wrappers.extend_exception_message")
    def test_attach_message_to_exception_with_debug_logs(self,
                                                         mock_extend,
                                                         mock_logger):
        mock_extend.side_effect = lambda e, msg: Exception(f"{e} {msg}")

        def faulty_func():
            raise RuntimeError("oops")

        decorated = wrappers.attach_message_to_exception(
            RuntimeError,
            "debug message",
            debug_logs="Debug info")(faulty_func)

        with self.assertRaises(Exception):
            decorated()

        mock_logger.error.assert_called_with("Debug info")
        mock_logger.exception.assert_called_once()

    def test_attach_message_to_exception_no_exception(self):
        func = Mock(return_value="ok")
        decorated = wrappers.attach_message_to_exception(ValueError, "extra")(func)
        result = decorated()
        self.assertEqual(result, "ok")
        func.assert_called_once()
