from unittest import TestCase, skip

import os
import sys
from requests import Request

from azure_functions_worker.testutils_lc import (
    LinuxConsumptionWebHostController
)


@skip('Flaky test and needs stabilization')
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

    def test_placeholder_mode_root_returns_ok(self):
        """In any circumstances, a placeholder container should returns 200
        even when it is not specialized.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            req = Request('GET', ctrl.url)
            resp = ctrl.send_request(req)
            self.assertTrue(resp.ok)

    def test_http_no_auth(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("HttpNoAuth")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            self.assertEqual(resp.status_code, 200)

    def test_common_libraries(self):
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
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("CommonLibraries")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            content = resp.json()
            self.assertIn('azure.functions', content)
            self.assertIn('azure.storage.blob', content)
            self.assertIn('numpy', content)
            self.assertIn('cryptography', content)
            self.assertIn('pyodbc', content)
            self.assertIn('requests', content)
            self.assertEqual(resp.status_code, 200)

    def test_new_protobuf(self):
        """A function app with the following requirements.txt:

        azure-functions==1.7.0
        protobuf==3.15.8
        grpcio==1.33.2

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("NewProtobuf")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            content = resp.json()

            # Worker always picks up the SDK version bundled with the image
            # Version of the packages are inconsistent due to isolation's bug
            self.assertIn('azure.functions', content)
            self.assertIn('google.protobuf', content)
            self.assertIn('grpc', content)
            self.assertEqual(resp.status_code, 200)

    def test_old_protobuf(self):
        """A function app with the following requirements.txt:

        azure-functions==1.5.0
        protobuf==3.8.0
        grpcio==1.27.1

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("NewProtobuf")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            content = resp.json()

            # Worker always picks up the SDK version bundled with the image
            # Version of the packages are inconsistent due to isolation's bug
            self.assertIn('azure.functions', content)
            self.assertIn('google.protobuf', content)
            self.assertIn('grpc', content)
            self.assertEqual(resp.status_code, 200)

    def _get_blob_url(self, scenario_name: str) -> str:
        return (
            f'https://pythonworker{self._py_shortform}sa.blob.core.windows.net/'
            f'python-worker-lc-apps/{scenario_name}{self._py_shortform}.zip'
        )
