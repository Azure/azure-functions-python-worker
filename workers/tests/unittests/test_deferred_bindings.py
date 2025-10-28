# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import unittest

import azure.functions as func
from tests.utils import testutils

if sys.version_info.minor < 13:
    from azure_functions_worker import protos
    from azure_functions_worker.bindings import meta

# Even if the tests are skipped for <=3.8, the library is still imported as
# it is used for these tests.
if sys.version_info.minor >= 9:
    from azurefunctions.extensions.base import GrpcClientType

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


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
@unittest.skipIf(sys.version_info.minor >= 13, "For python 3.13+,"
                                               "this logic is in the"
                                               "library worker.")
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
@unittest.skipIf(sys.version_info.minor >= 13, "For python 3.13+,"
                                               "this logic is in the"
                                               "library worker.")
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
@unittest.skipIf(sys.version_info.minor >= 13, "For python 3.13+,"
                                               "this logic is in the"
                                               "library worker.")
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
    def setUp(self):
        # Initialize DEFERRED_BINDING_REGISTRY
        meta.load_binding_registry()

    async def test_valid_settlement_param(self):
        params = {'param1', 'param2', 'param3'}
        bound_params = {'param1', 'param2'}
        annotations = {
            'param1': func.InputStream,
            'param2': func.Out[str],
            'param3': GrpcClientType
        }

        settlement_client_arg = meta.validate_settlement_param(
            params, bound_params, annotations)

        self.assertEqual(settlement_client_arg, 'param3')

    async def test_invalid_settlement_param(self):
        params = {'param1', 'param2', 'param3'}
        bound_params = {'param1', 'param2'}
        annotations = {
            'param1': func.InputStream,
            'param2': func.Out[str],
            'param3': str
        }

        settlement_client_arg = meta.validate_settlement_param(
            params, bound_params, annotations)

        self.assertEqual(settlement_client_arg, None)

    async def test_invalid_settlement_param_multiple(self):
        params = {'param1', 'param2', 'param3', 'param4'}
        bound_params = {'param1', 'param2'}
        annotations = {
            'param1': func.InputStream,
            'param2': func.Out[str],
            'param3': GrpcClientType,
            'param4': str
        }

        settlement_client_arg = meta.validate_settlement_param(
            params, bound_params, annotations)

        self.assertEqual(settlement_client_arg, None)
