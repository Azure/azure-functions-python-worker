# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func
import azurefunctions.extensions.base as clients
import tests.protos as protos

from azure_functions_runtime.bindings import datumdef, meta
from tests.utils import testutils
from tests.utils.mock_classes import MockMBD, MockCMBD


from azurefunctions.extensions.bindings.blob import (BlobClient,
                                                     ContainerClient,
                                                     StorageStreamDownloader)
from azurefunctions.extensions.bindings.eventhub import EventData, EventDataConverter
from azurefunctions.extensions.base import GrpcClientType

EVENTHUB_SAMPLE_CONTENT = b"\x00Sr\xc1\x8e\x08\xa3\x1bx-opt-sequence-number-epochT\xff\xa3\x15x-opt-sequence-numberU\x04\xa3\x0cx-opt-offset\x81\x00\x00\x00\x01\x00\x00\x010\xa3\x13x-opt-enqueued-time\x00\xa3\x1dcom.microsoft:datetime-offset\x81\x08\xddW\x05\xc3Q\xcf\x10\x00St\xc1I\x02\xa1\rDiagnostic-Id\xa1700-bdc3fde4889b4e907e0c9dcb46ff8d92-21f637af293ef13b-00\x00Su\xa0\x08message1"  # noqa: E501


class TestDeferredBindingsEnabled(testutils.AsyncTestCase):
    def setUp(self):
        # Initialize DEFERRED_BINDING_REGISTRY
        meta.load_binding_registry()

    def test_cmbd_deferred_bindings_enabled_decode(self):
        binding = EventDataConverter
        pb = protos.ParameterBinding(name='test',
                                     data=protos.TypedData(
                                         string='test'))
        sample_mbd = MockMBD(version="1.0",
                             source="AzureEventHubsEventData",
                             content_type="application/octet-stream",
                             content=EVENTHUB_SAMPLE_CONTENT)
        sample_cmbd = MockCMBD(model_binding_data=[sample_mbd, sample_mbd])
        datum = datumdef.Datum(value=sample_cmbd, type='collection_model_binding_data')

        obj = meta.deferred_bindings_decode(binding=binding, pb=pb,
                                            pytype=EventData, datum=datum, metadata={},
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
        meta.DEFERRED_BINDING_REGISTRY = clients.get_binding_registry()

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
