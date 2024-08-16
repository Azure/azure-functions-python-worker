# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import unittest

import azure.functions as func
from tests.utils import testutils

from azure_functions_worker import protos
from azure_functions_worker.bindings import datumdef, meta

# Even if the tests are skipped for <=3.8, the library is still imported as
# it is used for these tests.
if sys.version_info.minor >= 9:
    from azurefunctions.extensions.bindings.blob import (BlobClient,
                                                         BlobClientConverter,
                                                         ContainerClient,
                                                         StorageStreamDownloader)

DEFERRED_BINDINGS_ENABLED_DIR = testutils.EXTENSION_TESTS_FOLDER / \
    'deferred_bindings_tests' / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled'
DEFERRED_BINDINGS_DISABLED_DIR = testutils.EXTENSION_TESTS_FOLDER / \
    'deferred_bindings_tests' / \
    'deferred_bindings_functions' / \
    'deferred_bindings_disabled'
DEFERRED_BINDINGS_ENABLED_DUAL_DIR = testutils.EXTENSION_TESTS_FOLDER / \
    'deferred_bindings_tests' / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled_dual'


class MockMBD:
    def __init__(self, version: str, source: str,
                 content_type: str, content: str):
        self.version = version
        self.source = source
        self.content_type = content_type
        self.content = content


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsEnabled(testutils.AsyncTestCase):

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_enabled_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
        del sys.modules['function_app']

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_enabled_log(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            enabled_log_present = False
            for log in r.logs:
                message = log.message
                if "Deferred bindings enabled: True" in message:
                    enabled_log_present = True
                    break
            self.assertTrue(enabled_log_present)
        del sys.modules['function_app']


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsDisabled(testutils.AsyncTestCase):

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_disabled_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_DISABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
        del sys.modules['function_app']

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_disabled_log(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_DISABLED_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            disabled_log_present = False
            for log in r.logs:
                message = log.message
                if "Deferred bindings enabled: False" in message:
                    disabled_log_present = True
                    break
            self.assertTrue(disabled_log_present)
        del sys.modules['function_app']


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsEnabledDual(testutils.AsyncTestCase):

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_dual_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DUAL_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
        del sys.modules['function_app']

    @testutils.retryable_test(3, 5)
    async def test_deferred_bindings_dual_enabled_log(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DUAL_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            enabled_log_present = False
            for log in r.logs:
                message = log.message
                if "Deferred bindings enabled: True" in message:
                    enabled_log_present = True
                    break
            self.assertTrue(enabled_log_present)
        del sys.modules['function_app']


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsHelpers(testutils.AsyncTestCase):

    def test_deferred_bindings_enabled_decode(self):
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
                                            pytype=BlobClient, datum=datum, metadata={},
                                            function_name="test_function")

        self.assertIsNotNone(obj)

    async def test_check_deferred_bindings_enabled(self):
        """
        check_deferred_bindings_enabled checks if deferred bindings is enabled at fx
        and single binding level.

        The first bool represents if deferred bindings is enabled at a fx level. This
        means that at least one binding in the function is a deferred binding type.

        The second represents if the current binding is deferred binding. If this is
        True, then deferred bindings must also be enabled at the function level.
        """
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DIR) as host:
            await host.init_worker()

            # Type is not supported, deferred_bindings_enabled is not yet set
            self.assertEqual(meta.check_deferred_bindings_enabled(
                func.InputStream, False), (False, False))

            # Type is not supported, deferred_bindings_enabled already set
            self.assertEqual(meta.check_deferred_bindings_enabled(
                func.InputStream, True), (True, False))

            # Type is supported, deferred_bindings_enabled is not yet set
            self.assertEqual(meta.check_deferred_bindings_enabled(
                BlobClient, False), (True, True))
            self.assertEqual(meta.check_deferred_bindings_enabled(
                ContainerClient, False), (True, True))
            self.assertEqual(meta.check_deferred_bindings_enabled(
                StorageStreamDownloader, False), (True, True))

            # Type is supported, deferred_bindings_enabled is already set
            self.assertEqual(meta.check_deferred_bindings_enabled(
                BlobClient, True), (True, True))
            self.assertEqual(meta.check_deferred_bindings_enabled(
                ContainerClient, True), (True, True))
            self.assertEqual(meta.check_deferred_bindings_enabled(
                StorageStreamDownloader, True), (True, True))
