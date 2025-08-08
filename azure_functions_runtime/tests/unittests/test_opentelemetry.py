# Copyright (c) Microsoft Corporation. All rights reserved.
import os
import unittest

import tests.protos as protos

from azure_functions_runtime.handle_event import otel_manager, worker_init_request
from azure_functions_runtime.otel import (initialize_azure_monitor,
                                            update_opentelemetry_status)
from azure_functions_runtime.logging import logger
from tests.utils.constants import UNIT_TESTS_FOLDER
from tests.utils.mock_classes import FunctionRequest, Request, WorkerRequest
from unittest.mock import MagicMock, patch


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
    @patch("azure_functions_runtime.otel.update_opentelemetry_status")
    def test_initialize_azure_monitor_success(
        self,
        mock_update_ot,
        mock_imports,
    ):
        mock_imports.return_value = MagicMock()
        initialize_azure_monitor()
        mock_update_ot.assert_called_once()
        self.assertTrue(otel_manager.get_azure_monitor_available())

    @patch("azure_functions_runtime.otel.update_opentelemetry_status")
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
