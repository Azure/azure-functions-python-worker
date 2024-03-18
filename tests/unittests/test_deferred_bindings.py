# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import unittest

from azure_functions_worker import protos
from azure_functions_worker.bindings import meta
from tests.utils import testutils

DEFERRED_BINDINGS_ENABLED_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled'
DEFERRED_BINDINGS_DISABLED_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_disabled'

DEFERRED_BINDINGS_ENABLED_DUAL_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled_dual'


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
            self.assertTrue(meta.deferred_bindings_enabled)


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
