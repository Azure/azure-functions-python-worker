# Copyright (c) Microsoft Corporation. All rights reserved.
import os
import unittest

import tests.protos as protos

from azure_functions_runtime_v1.handle_event import (otel_manager, worker_init_request,
                                                       invocation_request)
from azure_functions_runtime_v1.otel import (initialize_azure_monitor,
                                             update_opentelemetry_status)
from azure_functions_runtime_v1.logging import logger
from tests.utils.constants import UNIT_TESTS_FOLDER
from tests.utils.mock_classes import FunctionRequest, Request, WorkerRequest
from tests.utils import testutils
from unittest.mock import AsyncMock, MagicMock, patch


FUNCTION_APP_DIRECTORY = UNIT_TESTS_FOLDER / 'basic_functions'


class TestOpenTelemetry(unittest.TestCase):

    def test_update_opentelemetry_status_import_error(self):
        with patch.dict('sys.modules', {
            'opentelemetry': None,
            'opentelemetry.context': None,
            'opentelemetry.trace': None,
            'opentelemetry.trace.propagation': None,
            'opentelemetry.trace.propagation.tracecontext': None,
        }):
            # Verify that context variables are None due to ImportError
            with self.assertLogs(logger.name, 'ERROR') as cm:
                update_opentelemetry_status()
                self.assertTrue(
                    any("Cannot import OpenTelemetry libraries."
                        in message for message in cm.output)
                )

    @patch('builtins.__import__')
    def test_update_opentelemetry_status_success(
            self, mock_imports):
        mock_imports.return_value = MagicMock()
        update_opentelemetry_status()
        self.assertIsNotNone(otel_manager.get_context_api())
        self.assertIsNotNone(otel_manager.get_trace_context_propagator())

    @patch('builtins.__import__')
    @patch("azure_functions_runtime_v1.otel.update_opentelemetry_status")
    def test_initialize_azure_monitor_success(
        self,
        mock_update_ot,
        mock_imports,
    ):
        mock_imports.return_value = MagicMock()
        initialize_azure_monitor()
        mock_update_ot.assert_called_once()
        self.assertTrue(otel_manager.get_azure_monitor_available())

    @patch("azure_functions_runtime_v1.otel.update_opentelemetry_status")
    def test_initialize_azure_monitor_import_error(
        self,
        mock_update_ot,
    ):
        with patch('builtins.__import__', side_effect=ImportError):
            initialize_azure_monitor()
            mock_update_ot.assert_called_once()
            # Verify that azure_monitor_available is set to False due to ImportError
            self.assertFalse(otel_manager.get_azure_monitor_available())

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'true'})
    @patch('builtins.__import__')
    async def test_init_request_initialize_azure_monitor_enabled_app_setting(
            self,
            mock_imports,
    ):
        mock_imports.return_value = MagicMock()

        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           FUNCTION_APP_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        init_response = await worker_init_request(worker_request)

        self.assertEqual(init_response.result.status,
                         protos.StatusResult.Success)

        # Verify azure_monitor_available is set to True
        self.assertTrue(otel_manager.get_azure_monitor_available())
        # Verify that WorkerOpenTelemetryEnabled capability is set to _TRUE
        capabilities = init_response.capabilities
        self.assertIn("WorkerOpenTelemetryEnabled", capabilities)
        self.assertEqual(capabilities["WorkerOpenTelemetryEnabled"], "true")

    @patch("azure_functions_runtime.handle_event."
           "otel_manager.initialize_azure_monitor")
    async def test_init_request_initialize_azure_monitor_default_app_setting(
        self,
        mock_initialize_azmon,
    ):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           FUNCTION_APP_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        init_response = await worker_init_request(worker_request)

        self.assertEqual(init_response.result.status,
                         protos.StatusResult.Success)

        # Azure monitor initialized not called
        # Since default behavior is not enabled
        mock_initialize_azmon.assert_not_called()

        # Verify azure_monitor_available is set to False
        self.assertFalse(otel_manager.get_azure_monitor_available())
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'false'})
    @patch("azure_functions_runtime.otel_manager.initialize_azure_monitor")
    async def test_init_request_initialize_azure_monitor_disabled_app_setting(
        self,
        mock_initialize_azmon,
    ):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           FUNCTION_APP_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        init_response = await worker_init_request(worker_request)

        self.assertEqual(init_response.result.status,
                         protos.StatusResult.Success)

        # Azure monitor initialized not called
        mock_initialize_azmon.assert_not_called()

        # Verify azure_monitor_available is set to False
        self.assertFalse(otel_manager.get_azure_monitor_available())
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)

    @patch.dict(os.environ, {'PYTHON_ENABLE_OPENTELEMETRY': 'true'})
    async def test_init_request_enable_opentelemetry_enabled_app_setting(
        self,
    ):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           FUNCTION_APP_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        init_response = await worker_init_request(worker_request)

        self.assertEqual(init_response.result.status,
                         protos.StatusResult.Success)

        # Verify otel_libs_available is set to True
        self.assertTrue(otel_manager.get_azure_monitor_available())
        # Verify that WorkerOpenTelemetryEnabled capability is set to _TRUE
        capabilities = init_response.capabilities
        self.assertIn("WorkerOpenTelemetryEnabled", capabilities)
        self.assertEqual(capabilities["WorkerOpenTelemetryEnabled"], "true")

    @patch.dict(os.environ, {'PYTHON_ENABLE_OPENTELEMETRY': 'false'})
    async def test_init_request_enable_opentelemetry_default_app_setting(
        self,
    ):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           FUNCTION_APP_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        init_response = await worker_init_request(worker_request)

        self.assertEqual(init_response.result.status,
                         protos.StatusResult.Success)

        # Verify otel_libs_available is set to False by default
        self.assertFalse(otel_manager.get_otel_libs_available())
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'false'})
    async def test_init_request_enable_azure_monitor_disabled_app_setting(
        self,
    ):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           FUNCTION_APP_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        init_response = await worker_init_request(worker_request)

        self.assertEqual(init_response.result.status,
                         protos.StatusResult.Success)

        # Verify otel_libs_available is set to False by default
        self.assertFalse(otel_manager.get_azure_monitor_available())
        # Verify that WorkerOpenTelemetryEnabled capability is not set
        capabilities = init_response.capabilities
        self.assertNotIn("WorkerOpenTelemetryEnabled", capabilities)


class TestOpenTelemetryContextPropagation(testutils.AsyncTestCase):
    """Tests to verify OpenTelemetry context is propagated before logging in v1.

    Issue #1626: OpenTelemetry context must be configured before the first
    log is emitted in invocation_request to ensure all logs have proper
    Operation Id in Application Insights.
    """

    def setUp(self):
        self.call_order = []

    def _track_configure_otel(self, *args, **kwargs):
        self.call_order.append('configure_opentelemetry')

    def _track_logger_info(self, *args, **kwargs):
        self.call_order.append('logger_info')

    def _make_mock_request(self, invocation_id="test-inv-id",
                           function_id="test-func-id"):
        """Create a minimal mock invocation request."""
        mock_invoc = MagicMock()
        mock_invoc.invocation_id = invocation_id
        mock_invoc.function_id = function_id
        mock_invoc.input_data = []

        mock_request = MagicMock()
        mock_request.request.invocation_request = mock_invoc
        return mock_request

    def _make_mock_fi(self):
        """Create a minimal mock FunctionInfo."""
        mock_fi = MagicMock()
        mock_fi.name = "test_function"
        mock_fi.is_async = True
        mock_fi.directory = "/test/dir"
        mock_fi.input_types = {}
        mock_fi.output_types = {}
        mock_fi.requires_context = False
        mock_fi.has_return = False
        mock_fi.return_type = None
        return mock_fi

    @patch("azure_functions_runtime_v1.handle_event"
           ".otel_manager.get_azure_monitor_available", return_value=True)
    @patch("azure_functions_runtime_v1.handle_event"
           ".otel_manager.get_otel_libs_available", return_value=False)
    @patch("azure_functions_runtime_v1.handle_event.execute_async",
           new_callable=AsyncMock)
    @patch("azure_functions_runtime_v1.handle_event.get_context")
    @patch("azure_functions_runtime_v1.handle_event._functions")
    @patch("azure_functions_runtime_v1.handle_event.configure_opentelemetry")
    @patch("azure_functions_runtime_v1.handle_event.logger")
    async def test_otel_configured_before_first_log_azure_monitor(
        self,
        mock_logger,
        mock_configure_otel,
        mock_functions,
        mock_get_context,
        mock_execute_async,
        mock_get_otel_libs,
        mock_get_azure_monitor,
    ):
        """Verify configure_opentelemetry is called before first log (Azure Monitor)."""
        mock_logger.info.side_effect = self._track_logger_info
        mock_configure_otel.side_effect = self._track_configure_otel
        mock_functions.get_function.return_value = self._make_mock_fi()
        mock_get_context.return_value = MagicMock()
        mock_execute_async.return_value = None

        try:
            await invocation_request(self._make_mock_request())
        except Exception:
            pass

        self.assertIn('configure_opentelemetry', self.call_order,
                      "configure_opentelemetry should have been called")
        self.assertIn('logger_info', self.call_order,
                      "logger.info should have been called")

        otel_index = self.call_order.index('configure_opentelemetry')
        first_log_index = self.call_order.index('logger_info')
        self.assertLess(
            otel_index, first_log_index,
            f"configure_opentelemetry (index {otel_index}) should be called "
            f"before the first logger.info (index {first_log_index}). "
            f"Call order: {self.call_order}"
        )

    @patch("azure_functions_runtime_v1.handle_event"
           ".otel_manager.get_azure_monitor_available", return_value=False)
    @patch("azure_functions_runtime_v1.handle_event"
           ".otel_manager.get_otel_libs_available", return_value=True)
    @patch("azure_functions_runtime_v1.handle_event.execute_async",
           new_callable=AsyncMock)
    @patch("azure_functions_runtime_v1.handle_event.get_context")
    @patch("azure_functions_runtime_v1.handle_event._functions")
    @patch("azure_functions_runtime_v1.handle_event.configure_opentelemetry")
    @patch("azure_functions_runtime_v1.handle_event.logger")
    async def test_otel_configured_before_first_log_otel_libs(
        self,
        mock_logger,
        mock_configure_otel,
        mock_functions,
        mock_get_context,
        mock_execute_async,
        mock_get_otel_libs,
        mock_get_azure_monitor,
    ):
        """Verify configure_opentelemetry is called before first log (otel libs)."""
        mock_logger.info.side_effect = self._track_logger_info
        mock_configure_otel.side_effect = self._track_configure_otel
        mock_functions.get_function.return_value = self._make_mock_fi()
        mock_get_context.return_value = MagicMock()
        mock_execute_async.return_value = None

        try:
            await invocation_request(self._make_mock_request())
        except Exception:
            pass

        self.assertIn('configure_opentelemetry', self.call_order,
                      "configure_opentelemetry should have been called")
        self.assertIn('logger_info', self.call_order,
                      "logger.info should have been called")

        otel_index = self.call_order.index('configure_opentelemetry')
        first_log_index = self.call_order.index('logger_info')
        self.assertLess(
            otel_index, first_log_index,
            f"configure_opentelemetry (index {otel_index}) should be called "
            f"before the first logger.info (index {first_log_index}). "
            f"Call order: {self.call_order}"
        )
