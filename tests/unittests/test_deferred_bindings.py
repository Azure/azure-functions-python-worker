# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from azure_functions_worker import protos
from tests.utils import testutils
from azure_functions_worker.bindings import meta

DEFERRED_BINDINGS_ENABLED_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_enabled'
DEFERRED_BINDINGS_DISABLED_DIR = testutils.UNIT_TESTS_FOLDER / \
    'deferred_bindings_functions' / \
    'deferred_bindings_disabled'


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
