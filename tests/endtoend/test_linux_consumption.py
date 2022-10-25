# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
from unittest import TestCase, skipIf

from requests import Request

from tests.utils.testutils_lc import (
    LinuxConsumptionWebHostController
)

_DEFAULT_HOST_VERSION = "4"


@skipIf(sys.version_info >= (3, 10, 0),
        "Skip the tests for Python 3.10 and above")
class TestLinuxConsumption(TestCase):
    """Test worker behaviors on specific scenarios.

    SCM_RUN_FROM_PACKAGE: built function apps are acquired from
        -> "Simple Batch" Subscription
        -> "AzureFunctionsPythonWorkerCILinuxDevOps" Resource Group
        -> "pythonworker<python_major><python_minor>sa" Storage Account
        -> "python-worker-lc-apps" Blob Container

    For a list of scenario names:
        https://pythonworker39sa.blob.core.windows.net/python-worker-lc-apps?restype=container&comp=list
    """

    @classmethod
    def setUpClass(cls):
        cls._py_version = f'{sys.version_info.major}.{sys.version_info.minor}'
        cls._py_shortform = f'{sys.version_info.major}{sys.version_info.minor}'

        cls._storage = os.getenv('AzureWebJobsStorage')
        if cls._storage is None:
            raise RuntimeError('Environment variable AzureWebJobsStorage is '
                               'required before running Linux Consumption test')

    async def test_placeholder_mode_root_returns_ok(self):
        """In any circumstances, a placeholder container should returns 200
        even when it is not specialized.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            req = Request('GET', ctrl.url)
            resp = ctrl.send_request(req)
            await self.assertTrue(resp.ok)

    async def test_http_no_auth(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("HttpNoAuth")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            await self.assertEqual(resp.status_code, 200)

    async def test_common_libraries(self):
        """A function app with the following requirements.txt:

        azure-functions
        azure-eventhub
        azure-storage-blob
        numpy
        cryptography
        pyodbc
        requests

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("CommonLibraries")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            await self.assertEqual(resp.status_code, 200)
            content = resp.json()
            await self.assertIn('azure.functions', content)
            await self.assertIn('azure.storage.blob', content)
            await self.assertIn('numpy', content)
            await self.assertIn('cryptography', content)
            await self.assertIn('pyodbc', content)
            await self.assertIn('requests', content)

    async def test_new_protobuf(self):
        """A function app with the following requirements.txt:

        azure-functions==1.7.0
        protobuf==3.15.8
        grpcio==1.33.2

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("NewProtobuf")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            await self.assertEqual(resp.status_code, 200)

            content = resp.json()

            # Worker always picks up the SDK version bundled with the image
            # Version of the packages are inconsistent due to isolation's bug
            await self.assertEqual(content['azure.functions'], '1.7.0')
            await self.assertEqual(content['google.protobuf'], '3.15.8')
            await self.assertEqual(content['grpc'], '1.33.2')

    async def test_old_protobuf(self):
        """A function app with the following requirements.txt:

        azure-functions==1.5.0
        protobuf==3.8.0
        grpcio==1.27.1

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("OldProtobuf")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            await self.assertEqual(resp.status_code, 200)

            content = resp.json()

            # Worker always picks up the SDK version bundled with the image
            # Version of the packages are inconsistent due to isolation's bug
            await self.assertIn(content['azure.functions'], '1.5.0')
            await self.assertIn(content['google.protobuf'], '3.8.0')
            await self.assertIn(content['grpc'], '1.27.1')

    async def test_debug_logging_disabled(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200 and by default customer debug logging should be
        disabled.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("EnableDebugLogging")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger1')
            resp = ctrl.send_request(req)

            await self.assertEqual(resp.status_code, 200)
            container_log = ctrl.get_container_logs()
            func_start_idx = container_log.find(
                "Executing 'Functions.HttpTrigger1'")
            await self.assertTrue(func_start_idx > -1,
                            "HttpTrigger function is not executed.")
            func_log = container_log[func_start_idx:]

            await self.assertIn('logging info', func_log)
            await self.assertIn('logging warning', func_log)
            await self.assertIn('logging error', func_log)
            await self.assertNotIn('logging debug', func_log)

    async def test_debug_logging_enabled(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200 and with customer debug logging enabled, debug logs
        should be written to container logs.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url(
                    "EnableDebugLogging"),
                "PYTHON_ENABLE_DEBUG_LOGGING": "1"
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger1')
            resp = ctrl.send_request(req)

            await self.assertEqual(resp.status_code, 200)
            container_log = ctrl.get_container_logs()
            func_start_idx = container_log.find(
                "Executing 'Functions.HttpTrigger1'")
            await self.assertTrue(func_start_idx > -1)
            func_log = container_log[func_start_idx:]

            await self.assertIn('logging info', func_log)
            await self.assertIn('logging warning', func_log)
            await self.assertIn('logging error', func_log)
            await self.assertIn('logging debug', func_log)

    async def test_pinning_functions_to_older_version(self):
        """An HttpTrigger function app with 'azure-functions==1.11.1' library
        should return 200 with the azure functions version set to 1.11.1
        since dependency isolation is enabled by default for all py versions
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:

            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url(
                    "PinningFunctions"),
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger1')
            resp = ctrl.send_request(req)

            await self.assertEqual(resp.status_code, 200)
            await self.assertIn("Func Version: 1.11.1", resp.text)

    def _get_blob_url(self, scenario_name: str) -> str:
        return (
            f'https://pythonworker{self._py_shortform}sa.blob.core.windows.net/'
            f'python-worker-lc-apps/{scenario_name}{self._py_shortform}.zip'
        )
