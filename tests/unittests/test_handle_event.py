# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Any
from unittest.mock import patch

import azure_functions_worker_v2.handle_event as handle_event
from azure_functions_worker_v2.handle_event import (worker_init_request,
                                                    functions_metadata_request,
                                                    function_environment_reload_request)
from tests.utils import testutils
from tests.utils.constants import UNIT_TESTS_FOLDER

import tests.protos as test_protos

BASIC_FUNCTION_DIRECTORY = UNIT_TESTS_FOLDER / "basic_function"
STREAMING_FUNCTION_DIRECTORY = UNIT_TESTS_FOLDER / "streaming_function"
INDEXING_EXCEPTION_FUNCTION_DIRECTORY = (UNIT_TESTS_FOLDER
                                         / "indexing_exception_function")


# This represents the top level protos request sent from the host
class WorkerRequest:
    def __init__(self, name: str, request: Any, properties: dict):
        self.name = name
        self.request = request
        self.properties = properties


# This represents the inner request
class Request:
    def __init__(self, name: Any):
        self.worker_init_request = name
        self.function_environment_reload_request = name


# This represents the Function Init/Metadata/Load/Invocation request
class FunctionRequest:
    def __init__(self, capabilities: Any, function_app_directory: Any):
        self.capabilities = capabilities
        self.function_app_directory = function_app_directory


class TestHandleEvent(testutils.AsyncTestCase):
    async def test_worker_init_request(self):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
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
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_worker_v2.handle_event.HttpV2Registry.http_v2_enabled",
           return_value=True)
    @patch("azure_functions_worker_v2.handle_event.initialize_http_server",
           return_value="http://mock_address")
    async def test_worker_init_request_with_streaming(self,
                                                      mock_http_v2_enabled,
                                                      mock_initialize_http_server):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           STREAMING_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await worker_init_request(worker_request)
        self.assertEqual(result.capabilities, {'WorkerStatus': 'true',
                                               'RpcHttpBodyOnly': 'true',
                                               'SharedMemoryDataTransfer': 'true',
                                               'RpcHttpTriggerMetadataRemoved': 'true',
                                               'RawHttpBodyBytes': 'true',
                                               'TypedDataCollection': 'true',
                                               'HttpUri': 'http://mock_address',
                                               'RequiresRouteParameters': 'true'})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_worker_v2.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=True)
    async def test_worker_init_request_with_otel(self, mock_otel_enabled):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await worker_init_request(worker_request)
        self.assertEqual(result.capabilities, {'WorkerStatus': 'true',
                                               'RpcHttpBodyOnly': 'true',
                                               'SharedMemoryDataTransfer': 'true',
                                               'RpcHttpTriggerMetadataRemoved': 'true',
                                               'RawHttpBodyBytes': 'true',
                                               'TypedDataCollection': 'true',
                                               'WorkerOpenTelemetryEnabled': 'true'})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    async def test_worker_init_request_with_exception(self):
        # Even if an exception happens during indexing,
        # we still return the WorkerInitResponse
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
        self.assertEqual(result.result.status, 1)

    async def test_functions_metadata_request(self):
        handle_event.protos = test_protos
        metadata_result = await functions_metadata_request(None)
        self.assertEqual(metadata_result.result.status, 1)


    def test_functions_metadata_request_with_exception(self):
        pass

    def test_invocation_request_sync(self):
        pass

    def test_invocation_request_async(self):
        pass

    def test_invocation_request_with_exception(self):
        pass

    @patch("azure_functions_worker_v2.loader.index_function_app",
           return_value=True)
    async def test_function_environment_reload_request(self):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.capabilities, {})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_worker_v2.handle_event.HttpV2Registry.http_v2_enabled",
           return_value=True)
    @patch("azure_functions_worker_v2.handle_event.initialize_http_server",
           return_value="http://mock_address")
    async def test_function_environment_reload_request_with_streaming(
            self,
            mock_http_v2_enabled,
            mock_initialize_http_server):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           STREAMING_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.capabilities, {'HttpUri': 'http://mock_address',
                                               'RequiresRouteParameters': 'true'})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_worker_v2.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=True)
    async def test_function_environment_reload_request_with_otel(self,
                                                                 mock_otel_enabled):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.capabilities, {'WorkerOpenTelemetryEnabled': 'true'})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    async def test_function_environment_reload_request_with_exception(self):
        # Even if an exception happens during indexing,
        # we still return success
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           INDEXING_EXCEPTION_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.capabilities, {})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)
