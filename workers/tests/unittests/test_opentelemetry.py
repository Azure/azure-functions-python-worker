import asyncio
import os
import unittest

from unittest.mock import MagicMock, patch

from tests.unittests.test_dispatcher import FUNCTION_APP_DIRECTORY
from tests.utils import testutils

from azure_functions_worker import protos
from azure_functions_worker.dispatcher import ContextEnabledTask


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


class TestOpenTelemetryContextPropagation(unittest.TestCase):
    """Tests to verify OpenTelemetry context is propagated before logging.

    Issue #1626: OpenTelemetry context must be configured before the first
    log is emitted in _handle__invocation_request to ensure all logs have
    proper Operation Id in Application Insights.
    """

    def setUp(self):
        # Import directly from azure_functions_worker so this test always tests
        # the correct dispatcher regardless of the Python version (testutils
        # redirects to proxy_worker on Python >= 3.13).
        from azure_functions_worker.dispatcher import Dispatcher, ContextEnabledTask
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        # Use ContextEnabledTask factory so dispatcher's assertion passes
        self.loop.set_task_factory(
            lambda loop, coro, context=None: ContextEnabledTask(
                coro, loop=loop, context=context))
        self.dispatcher = Dispatcher(
            self.loop, '127.0.0.1', 0,
            'test_worker_id', 'test_request_id',
            1.0, 1000)
        self.call_order = []

    def tearDown(self):
        self.loop.close()

    def _track_configure_otel(self, *args, **kwargs):
        """Track when configure_opentelemetry is called."""
        self.call_order.append('configure_opentelemetry')

    def _track_logger_info(self, *args, **kwargs):
        """Track when logger.info is called."""
        self.call_order.append('logger_info')

    @patch.dict(os.environ, {'PYTHON_ENABLE_OPENTELEMETRY': 'true'})
    @patch('azure_functions_worker.dispatcher.logger')
    def test_otel_configured_before_first_log_in_invocation_request(
            self,
            mock_logger,
    ):
        """Verify configure_opentelemetry is called before the first log.

        This test ensures that when OpenTelemetry is enabled, the context
        is propagated before any logging occurs, so all logs have proper
        trace context (Operation Id).
        """
        # Set up tracking for call order
        mock_logger.info.side_effect = self._track_logger_info

        # Enable OpenTelemetry on the dispatcher
        self.dispatcher._otel_libs_available = True
        self.dispatcher._azure_monitor_available = False

        # Mock configure_opentelemetry to track when it's called
        self.dispatcher.configure_opentelemetry = MagicMock(
            side_effect=self._track_configure_otel
        )

        # Mock _get_context to return a valid context
        mock_context = MagicMock()
        mock_context.trace_context = MagicMock()
        mock_context.trace_context.trace_parent = "00-trace-parent"
        mock_context.trace_context.trace_state = "state"
        mock_context.thread_local_storage = MagicMock()
        self.dispatcher._get_context = MagicMock(return_value=mock_context)

        # Mock the functions registry
        mock_fi = MagicMock()
        mock_fi.name = "test_function"
        mock_fi.is_async = True
        mock_fi.directory = "/test/dir"
        mock_fi.input_types = {}
        mock_fi.output_types = {}
        mock_fi.requires_context = False
        mock_fi.has_return = False
        mock_fi.settlement_client_arg = None
        mock_fi.func = MagicMock(return_value=None)
        self.dispatcher._functions = MagicMock()
        self.dispatcher._functions.get_function = MagicMock(return_value=mock_fi)

        # Create a mock invocation request
        invoc_request = protos.StreamingMessage(
            invocation_request=protos.InvocationRequest(
                invocation_id="test-inv-123",
                function_id="test-func-id",
                trace_context=protos.RpcTraceContext(
                    trace_parent="00-trace-parent",
                    trace_state="state"
                )
            )
        )

        # Mock _run_async_func to return None
        async def _noop():
            return None
        self.dispatcher._run_async_func = MagicMock(return_value=_noop())

        # Run the invocation request (will fail but we only care about call order)
        try:
            self.loop.run_until_complete(
                self.dispatcher._handle__invocation_request(invoc_request))
        except Exception:
            # We expect this may fail due to incomplete mocking,
            # but we only care about verifying call order
            pass

        # Assert both events were observed
        self.assertIn('configure_opentelemetry', self.call_order,
                      "configure_opentelemetry should have been called")
        self.assertIn('logger_info', self.call_order,
                      "logger.info should have been called")

        # Assert configure_opentelemetry was called before the first logger.info
        otel_index = self.call_order.index('configure_opentelemetry')
        first_log_index = self.call_order.index('logger_info')
        self.assertLess(
            otel_index, first_log_index,
            f"configure_opentelemetry (index {otel_index}) should be called "
            f"before the first logger.info (index {first_log_index}). "
            f"Call order: {self.call_order}"
        )

    @patch.dict(os.environ, {'PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY': 'true'})
    @patch('azure_functions_worker.dispatcher.logger')
    def test_azure_monitor_configured_before_first_log(
            self,
            mock_logger,
    ):
        """Verify configure_opentelemetry is called before first log with Azure Monitor."""
        # Set up tracking for call order
        mock_logger.info.side_effect = self._track_logger_info

        # Enable Azure Monitor on the dispatcher
        self.dispatcher._otel_libs_available = False
        self.dispatcher._azure_monitor_available = True

        # Mock configure_opentelemetry to track when it's called
        self.dispatcher.configure_opentelemetry = MagicMock(
            side_effect=self._track_configure_otel
        )

        # Mock _get_context to return a valid context
        mock_context = MagicMock()
        mock_context.trace_context = MagicMock()
        mock_context.trace_context.trace_parent = "00-trace-parent"
        mock_context.trace_context.trace_state = "state"
        mock_context.thread_local_storage = MagicMock()
        self.dispatcher._get_context = MagicMock(return_value=mock_context)

        # Mock the functions registry
        mock_fi = MagicMock()
        mock_fi.name = "test_function"
        mock_fi.is_async = True
        mock_fi.directory = "/test/dir"
        mock_fi.input_types = {}
        mock_fi.output_types = {}
        mock_fi.requires_context = False
        mock_fi.has_return = False
        mock_fi.settlement_client_arg = None
        mock_fi.func = MagicMock(return_value=None)
        self.dispatcher._functions = MagicMock()
        self.dispatcher._functions.get_function = MagicMock(return_value=mock_fi)

        # Create a mock invocation request
        invoc_request = protos.StreamingMessage(
            invocation_request=protos.InvocationRequest(
                invocation_id="test-inv-456",
                function_id="test-func-id",
                trace_context=protos.RpcTraceContext(
                    trace_parent="00-trace-parent",
                    trace_state="state"
                )
            )
        )

        # Mock _run_async_func to return None
        async def _noop():
            return None
        self.dispatcher._run_async_func = MagicMock(return_value=_noop())

        # Run the invocation request
        try:
            self.loop.run_until_complete(
                self.dispatcher._handle__invocation_request(invoc_request))
        except Exception:
            pass

        # Assert both events were observed
        self.assertIn('configure_opentelemetry', self.call_order,
                      "configure_opentelemetry should have been called")
        self.assertIn('logger_info', self.call_order,
                      "logger.info should have been called")

        # Assert configure_opentelemetry was called before the first logger.info
        otel_index = self.call_order.index('configure_opentelemetry')
        first_log_index = self.call_order.index('logger_info')
        self.assertLess(
            otel_index, first_log_index,
            f"configure_opentelemetry should be called before first log. "
            f"Call order: {self.call_order}"
        )
