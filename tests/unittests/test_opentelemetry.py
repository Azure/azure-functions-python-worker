import asyncio
import os
import sys
import unittest

from unittest import skipIf
from unittest.mock import MagicMock, patch

from tests.unittests.test_dispatcher import FUNCTION_APP_DIRECTORY
from tests.utils import testutils

from azure_functions_worker import protos


@skipIf(sys.version_info.minor == 7,
        "Packages are only supported for 3.8+")
class TestOpenTelemetry(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.dispatcher = testutils.create_dummy_dispatcher()

    def tearDown(self):
        self.loop.close()

    def test_update_opentelemetry_status_import_error(self):
        # Patch the built-in import mechanism
        with patch('builtins.__import__', side_effect=ImportError):
            self.dispatcher.update_opentelemetry_status()
            # Verify that context variables are None due to ImportError
            self.assertIsNone(self.dispatcher._context_api)
            self.assertIsNone(self.dispatcher._trace_context_propagator)

    @patch('builtins.__import__')
    def test_update_opentelemetry_status_success(
            self, mock_imports):
        mock_imports.return_value = MagicMock()
        self.dispatcher.update_opentelemetry_status()
        self.assertIsNotNone(self.dispatcher._context_api)
        self.assertIsNotNone(self.dispatcher._trace_context_propagator)

    @patch('builtins.__import__')
    @patch("azure_functions_worker.dispatcher.Dispatcher.update_opentelemetry_status")
    def test_initialize_azure_monitor_success(
        self,
        mock_update_ot,
        mock_imports,
    ):
        mock_imports.return_value = MagicMock()
        self.dispatcher.initialize_azure_monitor()
        mock_update_ot.assert_called_once()
        self.assertTrue(self.dispatcher._azure_monitor_available)

    @patch("azure_functions_worker.dispatcher.Dispatcher.update_opentelemetry_status")
    def test_initialize_azure_monitor_import_error(
        self,
        mock_update_ot,
    ):
        with patch('builtins.__import__', side_effect=ImportError):
            self.dispatcher.initialize_azure_monitor()
            mock_update_ot.assert_called_once()
            # Verify that azure_monitor_available is set to False due to ImportError
            self.assertFalse(self.dispatcher._azure_monitor_available)

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'true'})
    @patch('builtins.__import__')
    def test_init_request_initialize_azure_monitor_enabled_app_setting(
            self,
            mock_imports,
    ):
        mock_imports.return_value = MagicMock()

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        # Verify azure_monitor_available is set to True
        self.assertTrue(self.dispatcher._azure_monitor_available)
        # Verify that WorkerOpenTelemetryEnabled capability is set to _TRUE
        capabilities = init_response.worker_init_response.capabilities
        self.assertIn("WorkerOpenTelemetryEnabled", capabilities)
        self.assertEqual(capabilities["WorkerOpenTelemetryEnabled"], "true")

    @patch("azure_functions_worker.dispatcher.Dispatcher.initialize_azure_monitor")
    def test_init_request_initialize_azure_monitor_default_app_setting(
        self,
        mock_initialize_azmon,
    ):

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        # Azure monitor initialized not called
        # Since default behavior is not enabled
        mock_initialize_azmon.assert_not_called()

        # Verify azure_monitor_available is set to False
        self.assertFalse(self.dispatcher._azure_monitor_available)
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.worker_init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'false'})
    @patch("azure_functions_worker.dispatcher.Dispatcher.initialize_azure_monitor")
    def test_init_request_initialize_azure_monitor_disabled_app_setting(
        self,
        mock_initialize_azmon,
    ):

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        # Azure monitor initialized not called
        mock_initialize_azmon.assert_not_called()

        # Verify azure_monitor_available is set to False
        self.assertFalse(self.dispatcher._azure_monitor_available)
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.worker_init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)

    @patch.dict(os.environ, {'PYTHON_ENABLE_OPENTELEMETRY': 'true'})
    def test_init_request_enable_opentelemetry_enabled_app_setting(
        self,
    ):

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        # Verify otel_libs_available is set to True
        self.assertTrue(self.dispatcher._otel_libs_available)
        # Verify that WorkerOpenTelemetryEnabled capability is set to _TRUE
        capabilities = init_response.worker_init_response.capabilities
        self.assertIn("WorkerOpenTelemetryEnabled", capabilities)
        self.assertEqual(capabilities["WorkerOpenTelemetryEnabled"], "true")

    @patch.dict(os.environ, {'PYTHON_ENABLE_OPENTELEMETRY': 'false'})
    def test_init_request_enable_opentelemetry_default_app_setting(
        self,
    ):

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        # Verify otel_libs_available is set to False by default
        self.assertFalse(self.dispatcher._otel_libs_available)
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.worker_init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'false'})
    def test_init_request_enable_azure_monitor_disabled_app_setting(
        self,
    ):

        init_request = protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                host_version="2.3.4",
                function_app_directory=str(FUNCTION_APP_DIRECTORY)
            )
        )

        init_response = self.loop.run_until_complete(
            self.dispatcher._handle__worker_init_request(init_request))

        self.assertEqual(init_response.worker_init_response.result.status,
                         protos.StatusResult.Success)

        # Verify otel_libs_available is set to False by default
        self.assertFalse(self.dispatcher._otel_libs_available)
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.worker_init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)
