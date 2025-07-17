# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from unittest.mock import patch

import azure_functions_worker_v1.handle_event as handle_event
import tests.protos as test_protos

from azure_functions_worker_v1.handle_event import (worker_init_request,
                                                    functions_metadata_request,
                                                    function_environment_reload_request)
from tests.utils import testutils
from tests.utils.constants import UNIT_TESTS_FOLDER
from tests.utils.mock_classes import FunctionRequest, Request, WorkerRequest

BASIC_FUNCTION_DIRECTORY = UNIT_TESTS_FOLDER / "default_template"


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

    @patch("azure_functions_worker_v1.handle_event"
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

    async def test_functions_metadata_request(self):
        handle_event.protos = test_protos
        metadata_result = await functions_metadata_request(None)
        self.assertEqual(metadata_result.result.status, 1)

    async def test_function_environment_reload_request(self):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': test_protos})
        handle_event.protos = test_protos
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.capabilities, {})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    @patch("azure_functions_worker_v1.handle_event"
           ".otel_manager.get_azure_monitor_available",
           return_value=True)
    async def test_function_environment_reload_request_with_otel(self,
                                                                 mock_otel_enabled):
        handle_event.protos = test_protos
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
