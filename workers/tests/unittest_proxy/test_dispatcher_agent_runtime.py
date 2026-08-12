# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Unit tests for PYTHON_ENABLE_AGENT_RUNTIME environment variable logic
in dispatcher.reload_library_worker
"""
import builtins
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from proxy_worker.utils.constants import PYTHON_ENABLE_AGENT_RUNTIME
import proxy_worker.dispatcher as dispatcher_module


_real_import = builtins.__import__


class TestReloadLibraryWorkerAgentRuntime(unittest.TestCase):
    """Test suite for reload_library_worker with PYTHON_ENABLE_AGENT_RUNTIME env var"""

    def setUp(self):
        """Clear library worker state and environment before each test"""
        dispatcher_module._library_worker = None
        dispatcher_module._library_worker_has_cv = False

        # Clear environment variable
        if PYTHON_ENABLE_AGENT_RUNTIME in os.environ:
            del os.environ[PYTHON_ENABLE_AGENT_RUNTIME]

    def tearDown(self):
        """Clean up after each test"""
        dispatcher_module._library_worker = None
        dispatcher_module._library_worker_has_cv = False

        # Clear environment variable
        if PYTHON_ENABLE_AGENT_RUNTIME in os.environ:
            del os.environ[PYTHON_ENABLE_AGENT_RUNTIME]

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.importlib.import_module")
    @patch("proxy_worker.dispatcher.entry_points")
    def test_agent_runtime_enabled_with_true_string(
            self, mock_entry_points, mock_import_module, mock_logger):
        """Test that entry points are used when PYTHON_ENABLE_AGENT_RUNTIME='true'"""
        # Set environment variable to enable agent runtime
        os.environ[PYTHON_ENABLE_AGENT_RUNTIME] = "true"

        # Setup mock entry point
        mock_ep = Mock()
        mock_ep.name = "fastapi"
        mock_ep.load = Mock()
        mock_entry_points.return_value = [mock_ep]

        # Setup mock runtime base module
        mock_runtime_base = Mock()
        mock_runtime_base.RuntimeFeatureChecker.runtime_loaded.return_value = True
        mock_runtime_base.RuntimeTrackerMeta.get_module.return_value = (
            "azure_functions_fastapi.runtime")
        mock_runtime_base.RuntimeTrackerMeta.get_runtime_name.return_value = "fastapi"
        mock_runtime_base.RuntimeTrackerMeta.get_package_name.return_value = (
            "azure_functions_fastapi")

        # Setup mock runtime module
        mock_runtime_module = Mock()
        mock_runtime_module.VERSION = "2.0.0"
        mock_import_module.return_value = mock_runtime_module

        # Patch the runtime base import (including parent packages)
        mock_azurefunctions = Mock()
        mock_azurefunctions.extensions = Mock()
        mock_azurefunctions.extensions.base = mock_runtime_base
        with patch.dict(sys.modules, {
            'azurefunctions': mock_azurefunctions,
            'azurefunctions.extensions': mock_azurefunctions.extensions,
            'azurefunctions.extensions.base': mock_runtime_base
        }):
            dispatcher_module.Dispatcher.reload_library_worker("/home/site/wwwroot")

        # Verify entry points were queried
        mock_entry_points.assert_called_once_with(group='azurefunctions.runtimes')

        # Verify entry point was loaded
        mock_ep.load.assert_called_once()

        # Verify runtime module was imported
        mock_import_module.assert_called_with("azure_functions_fastapi")

        # Verify library worker was set
        self.assertEqual(dispatcher_module._library_worker, mock_runtime_module)

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.importlib.import_module")
    @patch("proxy_worker.dispatcher.entry_points")
    def test_agent_runtime_enabled_with_1_string(
            self, mock_entry_points, mock_import_module, mock_logger):
        """Test that entry points are used when PYTHON_ENABLE_AGENT_RUNTIME='1'"""
        # Set environment variable to enable agent runtime
        os.environ[PYTHON_ENABLE_AGENT_RUNTIME] = "1"

        # Setup mock entry point
        mock_ep = Mock()
        mock_ep.name = "test_runtime"
        mock_ep.load = Mock()
        mock_entry_points.return_value = [mock_ep]

        # Setup mock runtime base module
        mock_runtime_base = Mock()
        mock_runtime_base.RuntimeFeatureChecker.runtime_loaded.return_value = True
        mock_runtime_base.RuntimeTrackerMeta.get_module.return_value = (
            "test_package.runtime")
        mock_runtime_base.RuntimeTrackerMeta.get_runtime_name.return_value = (
            "test")
        mock_runtime_base.RuntimeTrackerMeta.get_package_name.return_value = (
            "test_package")

        # Setup mock runtime module
        mock_runtime_module = Mock()
        mock_runtime_module.VERSION = "1.0.0"
        mock_import_module.return_value = mock_runtime_module

        # Patch the runtime base import (including parent packages)
        mock_azurefunctions = Mock()
        mock_azurefunctions.extensions = Mock()
        mock_azurefunctions.extensions.base = mock_runtime_base
        with patch.dict(sys.modules, {
            'azurefunctions': mock_azurefunctions,
            'azurefunctions.extensions': mock_azurefunctions.extensions,
            'azurefunctions.extensions.base': mock_runtime_base
        }):
            dispatcher_module.Dispatcher.reload_library_worker("/home/site/wwwroot")

        # Verify entry points were queried (agent runtime path was used)
        mock_entry_points.assert_called_once_with(
            group='azurefunctions.runtimes')

        # Verify library worker was set
        self.assertEqual(dispatcher_module._library_worker, mock_runtime_module)

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.entry_points")
    @patch("proxy_worker.dispatcher.os.path.exists")
    @patch("builtins.__import__")
    def test_agent_runtime_disabled_uses_traditional_detection(
            self, mock_import, mock_exists, mock_entry_points, mock_logger):
        """Test that traditional detection is used when
        PYTHON_ENABLE_AGENT_RUNTIME is not set"""
        # Do NOT set PYTHON_ENABLE_AGENT_RUNTIME - should use traditional detection

        # Mock traditional fallback
        mock_exists.return_value = True  # v2 script exists

        mock_runtime_v2 = types.SimpleNamespace(
            __file__="azure_functions_runtime.py",
            invocation_id_cv=Mock(),
            VERSION="1.10.0"
        )

        def custom_import(name, *args, **kwargs):
            if name == "azure_functions_runtime":
                return mock_runtime_v2
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = custom_import

        # Clear sys.modules to force re-import
        if 'azure_functions_runtime' in sys.modules:
            del sys.modules['azure_functions_runtime']

        dispatcher_module.Dispatcher.reload_library_worker("/home/site/wwwroot")

        # Verify entry points were NOT queried
        mock_entry_points.assert_not_called()

        # Verify library worker was set to v2 via traditional detection
        self.assertEqual(dispatcher_module._library_worker, mock_runtime_v2)
        self.assertTrue(dispatcher_module._library_worker_has_cv)

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.entry_points")
    @patch("proxy_worker.dispatcher.os.path.exists")
    @patch("builtins.__import__")
    def test_agent_runtime_disabled_with_false_string(
            self, mock_import, mock_exists, mock_entry_points, mock_logger):
        """Test that traditional detection is used when
        PYTHON_ENABLE_AGENT_RUNTIME='false'"""
        # Set environment variable to disable agent runtime
        os.environ[PYTHON_ENABLE_AGENT_RUNTIME] = "false"

        # Mock traditional fallback
        mock_exists.return_value = False  # v2 script doesn't exist

        mock_runtime_v1 = types.SimpleNamespace(
            __file__="azure_functions_runtime_v1.py",
            VERSION="1.0.0"
        )

        def custom_import(name, *args, **kwargs):
            if name == "azure_functions_runtime_v1":
                return mock_runtime_v1
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = custom_import

        # Clear sys.modules to force re-import
        if 'azure_functions_runtime_v1' in sys.modules:
            del sys.modules['azure_functions_runtime_v1']

        dispatcher_module.Dispatcher.reload_library_worker("/home/site/wwwroot")

        # Verify entry points were NOT queried
        mock_entry_points.assert_not_called()

        # Verify library worker was set to v1 via traditional detection
        self.assertEqual(dispatcher_module._library_worker, mock_runtime_v1)
        self.assertFalse(dispatcher_module._library_worker_has_cv)

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.entry_points")
    @patch("proxy_worker.dispatcher.os.path.exists")
    @patch("builtins.__import__")
    def test_agent_runtime_disabled_with_0_string(
            self, mock_import, mock_exists, mock_entry_points, mock_logger):
        """Test that traditional detection is used when
        PYTHON_ENABLE_AGENT_RUNTIME='0'"""
        # Set environment variable to disable agent runtime
        os.environ[PYTHON_ENABLE_AGENT_RUNTIME] = "0"

        # Mock traditional fallback
        mock_exists.return_value = True

        mock_runtime_v2 = types.SimpleNamespace(
            __file__="azure_functions_runtime.py",
            invocation_id_cv=Mock(),
            VERSION="1.11.0"
        )

        def custom_import(name, *args, **kwargs):
            if name == "azure_functions_runtime":
                return mock_runtime_v2
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = custom_import

        # Clear sys.modules to force re-import
        if 'azure_functions_runtime' in sys.modules:
            del sys.modules['azure_functions_runtime']

        dispatcher_module.Dispatcher.reload_library_worker("/home/site/wwwroot")

        # Verify entry points were NOT queried
        mock_entry_points.assert_not_called()

        # Verify library worker was set via traditional detection
        self.assertEqual(dispatcher_module._library_worker, mock_runtime_v2)

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.entry_points")
    def test_agent_runtime_enabled_no_runtime_registered_fallback_still_used(
            self, mock_entry_points, mock_logger):
        """Test that when agent runtime is enabled but no runtime registers,
        we still use the traditional fallback within the agent runtime path"""
        # Set environment variable to enable agent runtime
        os.environ[PYTHON_ENABLE_AGENT_RUNTIME] = "true"

        # Setup mock entry points
        mock_entry_points.return_value = []

        # Setup mock runtime base module - no runtime registered
        mock_runtime_base = Mock()
        mock_runtime_base.RuntimeFeatureChecker.runtime_loaded.return_value = False

        # Mock traditional fallback
        with patch("proxy_worker.dispatcher.os.path.exists", return_value=True):
            with patch("builtins.__import__") as mock_import:
                mock_runtime_v2 = types.SimpleNamespace(
                    __file__="azure_functions_runtime.py",
                    invocation_id_cv=Mock(),
                    VERSION="1.12.0"
                )

                def custom_import(name, *args, **kwargs):
                    if name == "azure_functions_runtime":
                        return mock_runtime_v2
                    return _real_import(name, *args, **kwargs)

                mock_import.side_effect = custom_import

                # Patch the runtime base import (including parent packages)
                mock_azurefunctions = Mock()
                mock_azurefunctions.extensions = Mock()
                mock_azurefunctions.extensions.base = mock_runtime_base
                with patch.dict(sys.modules, {
                    'azurefunctions': mock_azurefunctions,
                    'azurefunctions.extensions': mock_azurefunctions.extensions,
                    'azurefunctions.extensions.base': mock_runtime_base
                }):
                    dispatcher_module.Dispatcher.reload_library_worker(
                        "/home/site/wwwroot")

        # When agent runtime is enabled, entry points are queried even if
        # no runtime registers
        mock_entry_points.assert_called_once_with(group='azurefunctions.runtimes')

        # Based on the updated implementation, when no runtime registers via
        # entry points, the dispatcher falls back to traditional detection
        # So we should have the v2 runtime loaded
        self.assertEqual(dispatcher_module._library_worker, mock_runtime_v2)
        self.assertTrue(dispatcher_module._library_worker_has_cv)

    @patch("proxy_worker.dispatcher.logger")
    @patch("proxy_worker.dispatcher.os.path.exists")
    @patch("builtins.__import__")
    def test_agent_runtime_disabled_logs_debug_fallback_message(
            self, mock_import, mock_exists, mock_logger):
        """Test that fallback message is logged when agent runtime is disabled"""
        # Ensure agent runtime is disabled (not set)
        if PYTHON_ENABLE_AGENT_RUNTIME in os.environ:
            del os.environ[PYTHON_ENABLE_AGENT_RUNTIME]

        # Mock traditional fallback
        mock_exists.return_value = True

        mock_runtime_v2 = types.SimpleNamespace(
            __file__="azure_functions_runtime.py",
            invocation_id_cv=Mock(),
            VERSION="1.13.0"
        )

        def custom_import(name, *args, **kwargs):
            if name == "azure_functions_runtime":
                return mock_runtime_v2
            return _real_import(name, *args, **kwargs)

        mock_import.side_effect = custom_import

        # Clear sys.modules to force re-import
        if 'azure_functions_runtime' in sys.modules:
            del sys.modules['azure_functions_runtime']

        dispatcher_module.Dispatcher.reload_library_worker("/home/site/wwwroot")

        # Verify traditional runtime import logged
        mock_logger.debug.assert_any_call(
            "azure_functions_runtime import succeeded: %s",
            "azure_functions_runtime.py"
        )
