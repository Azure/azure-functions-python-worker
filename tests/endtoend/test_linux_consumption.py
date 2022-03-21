# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
from unittest import TestCase, skipIf

from requests import Request

from azure_functions_worker.testutils_lc import (
    LinuxConsumptionWebHostController,
)
from azure_functions_worker.utils.common import is_python_version


@skipIf(
    is_python_version("3.10"),
    "Skip the tests for Python 3.10 currently as the mesh images for "
    "Python 3.10 aren't available currently.",
)
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
        cls._py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        cls._py_shortform = f"{sys.version_info.major}{sys.version_info.minor}"

        cls._storage = os.getenv("AzureWebJobsStorage")
        if cls._storage is None:
            raise RuntimeError(
                "Environment variable AzureWebJobsStorage is "
                "required before running Linux Consumption test"
            )

    def test_placeholder_mode_root_returns_ok(self):
        """In any circumstances, a placeholder container should returns 200
        even when it is not specialized.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            req = Request("GET", ctrl.url)
            resp = ctrl.send_request(req)
            self.assertTrue(resp.ok)

    def test_http_no_auth(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(
                env={
                    "AzureWebJobsStorage": self._storage,
                    "SCM_RUN_FROM_PACKAGE": self._get_blob_url("HttpNoAuth"),
                }
            )
            req = Request("GET", f"{ctrl.url}/api/HttpTrigger")
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
            ctrl.assign_container(
                env={
                    "AzureWebJobsStorage": self._storage,
                    "SCM_RUN_FROM_PACKAGE": self._get_blob_url(
                        "CommonLibraries"
                    ),
                }
            )
            req = Request("GET", f"{ctrl.url}/api/HttpTrigger")
            resp = ctrl.send_request(req)
            content = resp.json()
            self.assertIn("azure.functions", content)
            self.assertIn("azure.storage.blob", content)
            self.assertIn("numpy", content)
            self.assertIn("cryptography", content)
            self.assertIn("pyodbc", content)
            self.assertIn("requests", content)
            self.assertEqual(resp.status_code, 200)

    def test_new_protobuf(self):
        """A function app with the following requirements.txt:

        azure-functions==1.7.0
        protobuf==3.15.8
        grpcio==1.33.2

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(
                env={
                    "AzureWebJobsStorage": self._storage,
                    "SCM_RUN_FROM_PACKAGE": self._get_blob_url("NewProtobuf"),
                }
            )
            req = Request("GET", f"{ctrl.url}/api/HttpTrigger")
            resp = ctrl.send_request(req)
            content = resp.json()

            # Worker always picks up the SDK version bundled with the image
            # Version of the packages are inconsistent due to isolation's bug
            self.assertIn("azure.functions", content)
            self.assertIn("google.protobuf", content)
            self.assertIn("grpc", content)
            self.assertEqual(resp.status_code, 200)

    def test_old_protobuf(self):
        """A function app with the following requirements.txt:

        azure-functions==1.5.0
        protobuf==3.8.0
        grpcio==1.27.1

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(
                env={
                    "AzureWebJobsStorage": self._storage,
                    "SCM_RUN_FROM_PACKAGE": self._get_blob_url("NewProtobuf"),
                }
            )
            req = Request("GET", f"{ctrl.url}/api/HttpTrigger")
            resp = ctrl.send_request(req)
            content = resp.json()

            # Worker always picks up the SDK version bundled with the image
            # Version of the packages are inconsistent due to isolation's bug
            self.assertIn("azure.functions", content)
            self.assertIn("google.protobuf", content)
            self.assertIn("grpc", content)
            self.assertEqual(resp.status_code, 200)

    def test_debug_logging_disabled(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200 and by default customer debug logging should be
        disabled.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(
                env={
                    "AzureWebJobsStorage": self._storage,
                    "SCM_RUN_FROM_PACKAGE": self._get_blob_url(
                        "EnableDebugLogging"
                    ),
                }
            )
            req = Request("GET", f"{ctrl.url}/api/HttpTrigger1")
            resp = ctrl.send_request(req)

            self.assertEqual(resp.status_code, 200)
            container_log = ctrl.get_container_logs()
            func_start_idx = container_log.find(
                "Executing 'Functions.HttpTrigger1'"
            )
            self.assertTrue(
                func_start_idx > -1, "HttpTrigger function is not executed."
            )
            func_log = container_log[func_start_idx:]

            self.assertIn("logging info", func_log)
            self.assertIn("logging warning", func_log)
            self.assertIn("logging error", func_log)
            self.assertNotIn("logging debug", func_log)

    def test_debug_logging_enabled(self):
        """An HttpTrigger function app with 'azure-functions' library
        should return 200 and with customer debug logging enabled, debug logs
        should be written to container logs.
        """
        with LinuxConsumptionWebHostController("3", self._py_version) as ctrl:
            ctrl.assign_container(
                env={
                    "AzureWebJobsStorage": self._storage,
                    "SCM_RUN_FROM_PACKAGE": self._get_blob_url(
                        "EnableDebugLogging"
                    ),
                    "PYTHON_ENABLE_DEBUG_LOGGING": "1",
                }
            )
            req = Request("GET", f"{ctrl.url}/api/HttpTrigger1")
            resp = ctrl.send_request(req)

            self.assertEqual(resp.status_code, 200)
            container_log = ctrl.get_container_logs()
            func_start_idx = container_log.find(
                "Executing 'Functions.HttpTrigger1'"
            )
            self.assertTrue(func_start_idx > -1)
            func_log = container_log[func_start_idx:]

            self.assertIn("logging info", func_log)
            self.assertIn("logging warning", func_log)
            self.assertIn("logging error", func_log)
            self.assertIn("logging debug", func_log)

    def _get_blob_url(self, scenario_name: str) -> str:
        return (
            f"https://pythonworker{self._py_shortform}sa.blob.core.windows.net/"
            f"python-worker-lc-apps/{scenario_name}{self._py_shortform}.zip"
        )
