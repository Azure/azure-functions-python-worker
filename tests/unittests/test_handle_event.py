# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Any
from unittest.mock import patch

from azure_functions_worker_v2.handle_event import (worker_init_request,
                                                    functions_metadata_request,
                                                    function_environment_reload_request)
from tests.utils import testutils

import tests.protos as protos

BASIC_FUNCTION_DIRECTORY = "C:\\Users\\victoriahall\\Documents\\repos\\azure-functions-python-worker\\tests\\unittests\\basic_function"
STREAMING_FUNCTION_DIRECTORY = "C:\\Users\\victoriahall\\Documents\\repos\\azure-functions-python-worker\\tests\\unittests\\streaming_function"
INDEXING_EXCEPTION_FUNCTION_DIRECTORY = "tests\\unittests\\indexing_exception_function"


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
                                                   'protos': protos})
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

    async def test_worker_init_request_with_streaming(self):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           STREAMING_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        result = await worker_init_request(worker_request)
        self.assertNotEqual(result.capabilities, {'WorkerStatus': 'true',
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

    async def test_worker_init_request_with_exception(self):
        # Even if an exception happens during indexing,
        # we still return the WorkerInitResponse
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(FunctionRequest(
                                           'hello',
                                           INDEXING_EXCEPTION_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
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
        result = await self.run_init_then_meta()
        self.assertEqual(result.use_default_metadata_indexing, False)
        self.assertIsNotNone(result.function_metadata_results)
        self.assertEqual(result.result.status, 1)

    async def run_init_then_meta(self):
        worker_request = WorkerRequest(name='worker_init_request',
                                       request=Request(
                                           FunctionRequest('hello', BASIC_FUNCTION_DIRECTORY)),
                                       properties={'host': '123',
                                                   'protos': protos})
        _ = await worker_init_request(worker_request)
        result = await functions_metadata_request(worker_request)
        return result

    def test_functions_metadata_request_with_exception(self):
        pass

    def test_invocation_request_sync(self):
        pass

    def test_invocation_request_async(self):
        pass

    def test_invocation_request_with_exception(self):
        pass

    async def test_function_environment_reload_request(self):
        worker_request = WorkerRequest(name='function_environment_reload_request',
                                       request=Request(FunctionRequest('hello')),
                                       properties={'host': '123',
                                                   'protos': protos})
        result = await function_environment_reload_request(worker_request)
        self.assertEqual(result.capabilities, {})
        self.assertEqual(result.worker_metadata.runtime_name, "python")
        self.assertIsNotNone(result.worker_metadata.runtime_version)
        self.assertIsNotNone(result.worker_metadata.worker_version)
        self.assertIsNotNone(result.worker_metadata.worker_bitness)
        self.assertEqual(result.result.status, 1)

    def test_function_environment_reload_request_with_streaming(self):
        pass

    def test_function_environment_reload_request_with_exception(self):
        pass

    def test_load_function_metadata(self):
        pass

    def test_index_functions(self):
        pass
