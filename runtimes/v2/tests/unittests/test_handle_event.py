# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from unittest.mock import patch

import azure_functions_runtime.handle_event as handle_event
import tests.protos as test_protos

from azure_functions_runtime.handle_event import (worker_init_request,
                                                  functions_metadata_request,
                                                  function_load_request,
                                                  function_environment_reload_request)
from tests.utils import testutils
from tests.utils.constants import UNIT_TESTS_FOLDER
from tests.utils.mock_classes import FunctionRequest, Request, WorkerRequest


BASIC_FUNCTION_DIRECTORY = UNIT_TESTS_FOLDER / "basic_function"
STREAMING_FUNCTION_DIRECTORY = UNIT_TESTS_FOLDER / "streaming_function"
INDEXING_EXCEPTION_FUNCTION_DIRECTORY = (UNIT_TESTS_FOLDER
                                         / "indexing_exception_function")


class TestHandleEvent(testutils.AsyncTestCase):
    @patch("azure_functions_runtime.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=False)
    @patch("azure_functions_runtime.handle_event.load_function_metadata")
    async def test_worker_init_request(self, mock_load_function_metadata,
                                       mock_get_azure_monitor_available):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await worker_init_request(worker_request)
        mock_load_function_metadata.assert_called_once()
        self.assertEqual(result.capabilities, {'WorkerStatus': 'true',
                                               'RpcHttpBodyOnly': 'true',
                                               'SharedMemoryDataTransfer': 'true',
                                               'RpcHttpTriggerMetadataRemoved': 'true',
                                               'RawHttpBodyBytes': 'true',
                                               'TypedDataCollection': 'true'})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_runtime.handle_event.load_function_metadata")
    @patch("azure_functions_runtime.handle_event.HttpV2Registry.http_v2_enabled",
           return_value=True)
    @patch("azure_functions_runtime.handle_event.initialize_http_server",
           return_value="http://mock_address")
    async def test_worker_init_request_with_streaming(self,
                                                      mock_http_v2_enabled,
                                                      mock_initialize_http_server,
                                                      mock_load_function_metadata):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           STREAMING_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await worker_init_request(worker_request)
        mock_load_function_metadata.assert_called_once()
        self.assertEqual('http://mock_address', result.capabilities["HttpUri"])
        self.assertEqual('true', result.capabilities["RequiresRouteParameters"])
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_runtime.handle_event.load_function_metadata")
    @patch("azure_functions_runtime.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=True)
    async def test_worker_init_request_with_otel(self,
                                                 mock_otel_enabled,
                                                 mock_load_function_metadata):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await worker_init_request(worker_request)
        mock_load_function_metadata.assert_called_once()
        self.assertEqual('true', result.capabilities["WorkerOpenTelemetryEnabled"])
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_runtime.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=False)
    async def test_worker_init_request_with_exception(self,
                                                      mock_otel_enabled):
        # If an exception happens during indexing, we return failure
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           INDEXING_EXCEPTION_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await worker_init_request(worker_request)
        self.assertEqual(result.capabilities, {'WorkerStatus': 'true',
                                               'RpcHttpBodyOnly': 'true',
                                               'SharedMemoryDataTransfer': 'true',
                                               'RpcHttpTriggerMetadataRemoved': 'true',
                                               'RawHttpBodyBytes': 'true',
                                               'TypedDataCollection': 'true'})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 0)

    async def test_functions_metadata_request(self):
        # We always succeed in metadata request - exceptions are raised
        # in init
        handle_event.protos = test_protos
        metadata_result = await functions_metadata_request(None)
        self.assertEqual(metadata_result.result.status, 1)

    async def test_function_load_request(self):
        handle_event.protos = test_protos
        worker_request = WorkerRequest(name='function_load_request',
                                       request=Request(FunctionRequest(
                                           function_id="123")
                                       ),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_load_request(worker_request)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_runtime.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=False)
    @patch("azure_functions_runtime.handle_event.load_function_metadata")
    async def test_function_environment_reload_request(
            self,
            mock_load_function_metadata,
            mock_get_azure_monitor_available):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        handle_event.protos = test_protos
        result = await function_environment_reload_request(worker_request)
        mock_load_function_metadata.assert_called_once()
        self.assertEqual(result.capabilities, {})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_runtime.handle_event.load_function_metadata")
    @patch("azure_functions_runtime.handle_event.HttpV2Registry.http_v2_enabled",
           return_value=True)
    @patch("azure_functions_runtime.handle_event.initialize_http_server",
           return_value="http://mock_address")
    async def test_function_environment_reload_request_with_streaming(
            self,
            mock_http_v2_enabled,
            mock_initialize_http_server,
            mock_load_function_metadata):
        handle_event.protos = test_protos
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           STREAMING_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        mock_load_function_metadata.assert_called_once()
        self.assertEqual('http://mock_address', result.capabilities["HttpUri"])
        self.assertEqual('true', result.capabilities["RequiresRouteParameters"])
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_runtime.handle_event.load_function_metadata")
    @patch("azure_functions_runtime.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=True)
    async def test_function_environment_reload_request_with_otel(
            self,
            mock_otel_enabled,
            mock_load_function_metadata):
        handle_event.protos = test_protos
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        mock_load_function_metadata.assert_called_once()
        self.assertEqual('true', result.capabilities["WorkerOpenTelemetryEnabled"])
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    async def test_function_environment_reload_request_with_exception(self):
        # If an exception happens during indexing, the worker reports failure
        handle_event.protos = test_protos
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           INDEXING_EXCEPTION_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.result.status, 0)
