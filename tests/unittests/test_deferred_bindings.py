# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import unittest

from azure_functions_worker import protos
from azure_functions_worker.bindings import datumdef, meta
from tests.utils import testutils
from azure.functions.extension.blob import BlobClient, BlobClientConverter

DEFERRED_BINDINGS_ENABLED_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled'
DEFERRED_BINDINGS_DISABLED_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_disabled'

DEFERRED_BINDINGS_ENABLED_DUAL_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled_dual'


class MockMBD:
    def __init__(self, version: str, source: str,
                 content_type: str, content: str):
        self.version = version
        self.source = source
        self.content_type = content_type
        self.content = content


@unittest.skipIf(sys.version_info.minor <= 8,
                 "Run the tests only for Python 3.9+. The"
                 "SDK only supports Python 3.9+")
class TestDeferredBindingsEnabled(testutils.AsyncTestCase):

    async def test_deferred_bindings_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)


@unittest.skipIf(sys.version_info.minor <= 8,
                 "Run the tests only for Python 3.9+. The"
                 "SDK only supports Python 3.9+")
class TestDeferredBindingsEnabledDual(testutils.AsyncTestCase):

    async def test_deferred_bindings_dual_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DUAL_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)


@unittest.skipIf(sys.version_info.minor <= 8,
                 "Run the tests only for Python 3.9+. The"
                 "SDK only supports Python 3.9+")
class TestDeferredBindingsDisabled(testutils.AsyncTestCase):

    async def test_non_deferred_bindings_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_DISABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
            self.assertFalse(meta.deferred_bindings_enabled)


@unittest.skipIf(sys.version_info.minor <= 8,
                 "Run the tests only for Python 3.9+. The"
                 "SDK only supports Python 3.9+")
class TestDeferredBindingsHelpers(unittest.TestCase):

    def test_get_deferred_binding(self):
        bind_name = 'client'
        pytype = BlobClient(data={'version': '1.0',
                                  'source': 'AzureStorageBlobs',
                                  'content_type': 'application/json',
                                  'content': "{\"Connection\":\"AzureWebJobsStorage\","
                                             "\"ContainerName\":"
                                             "\"python-worker-tests\","
                                             "\"BlobName\":"
                                             "\"test-blobclient-trigger.txt\"}"})
        binding = meta.get_deferred_binding(bind_name=bind_name, pytype=pytype)
        self.assertIsInstance(binding, BlobClient)

    def test_get_non_deferred_binding(self):
        bind_name = 'blob'
        pytype = str
        binding = meta.get_deferred_binding(bind_name=bind_name, pytype=pytype)
        self.assertIsInstance(binding, None)

    def test_deferred_bindings_decode(self):
        binding = BlobClientConverter
        pb = protos.ParameterBinding(name='test',
                                     data=protos.TypedData(
                                         string='test'))
        sample_mbd = MockMBD(version="1.0",
                             source="AzureStorageBlobs",
                             content_type="application/json",
                             content="{\"Connection\":\"AzureWebJobsStorage\","
                                     "\"ContainerName\":"
                                     "\"python-worker-tests\","
                                     "\"BlobName\":"
                                     "\"test-blobclient-trigger.txt\"}")
        datum = datumdef.Datum(value=sample_mbd, type='model_binding_data')

        obj = meta.deferred_bindings_decode(binding=binding, pb=pb,
                                            pytype=BlobClient, datum=datum, metadata={})

        self.assertIsNotNone(obj)
