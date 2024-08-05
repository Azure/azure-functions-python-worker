# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import unittest

import azure.functions as func
from tests.utils import testutils

from azure_functions_worker import protos
from azure_functions_worker.bindings import meta

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
class TestDeferredBindingsEnabledDual(testutils.AsyncTestCase):

    async def test_deferred_bindings_dual_metadata(self):
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DUAL_DIR) as host:
            await host.init_worker()
            r = await host.get_functions_metadata()
            self.assertIsInstance(r.response, protos.FunctionMetadataResponse)
            self.assertEqual(r.response.result.status,
                             protos.StatusResult.Success)
        del sys.modules['function_app']

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
class TestDeferredBindingsDualHelpers(testutils.AsyncTestCase):

    async def test_check_deferred_bindings_dual_enabled(self):
        """
        check_deferred_bindings_enabled checks if deferred bindings is enabled at fx
        and single binding level.

        The first bool represents if deferred bindings is enabled at a fx level. This
        means that at least one binding in the function is a deferred binding type.

        The second represents if the current binding is deferred binding. If this is
        True, then deferred bindings must also be enabled at the function level.

        Test: type is not supported, deferred_bindings_enabled already set
        """
        async with testutils.start_mockhost(
                script_root=DEFERRED_BINDINGS_ENABLED_DUAL_DIR) as host:
            await host.init_worker()
            self.assertEqual(meta.check_deferred_bindings_enabled(
                func.InputStream, True), (True, False))
        del sys.modules['function_app']
