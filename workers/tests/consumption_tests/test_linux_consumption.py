# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
from time import sleep
from unittest import TestCase, skip, skipIf

from azure_functions_worker.constants import (
    PYTHON_ENABLE_DEBUG_LOGGING,
    PYTHON_ENABLE_INIT_INDEXING,
    PYTHON_ENABLE_WORKER_EXTENSIONS,
    PYTHON_ISOLATE_WORKER_DEPENDENCIES,
)
from requests import Request
from tests.utils.testutils_lc import LinuxConsumptionWebHostController

_DEFAULT_HOST_VERSION = "4"


class TestLinuxConsumption(TestCase):

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
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            req = Request('GET', ctrl.url)
            resp = ctrl.send_request(req)
            self.assertTrue(resp.ok)

    def test_http_no_auth(self):
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
            self.assertEqual(resp.status_code, 200)

    @skipIf(sys.version_info.minor != 11,
            "Uploaded common libraries are only supported for Python 3.11")
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
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("CommonLibraries")
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger')
            resp = ctrl.send_request(req)
            self.assertEqual(resp.status_code, 200)
            content = resp.json()
            self.assertIn('azure.functions', content)
            self.assertIn('azure.storage.blob', content)
            self.assertIn('numpy', content)
            self.assertIn('cryptography', content)
            self.assertIn('pyodbc', content)
            self.assertIn('requests', content)

    def test_debug_logging_disabled(self):
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

            self.assertEqual(resp.status_code, 200)
            container_log = ctrl.get_container_logs()
            func_start_idx = container_log.find(
                "Executing 'Functions.HttpTrigger1'")
            self.assertTrue(func_start_idx > -1,
                            "HttpTrigger function is not executed.")
            func_log = container_log[func_start_idx:]

            self.assertIn('logging info', func_log)
            self.assertIn('logging warning', func_log)
            self.assertIn('logging error', func_log)
            self.assertNotIn('logging debug', func_log)

    def test_debug_logging_enabled(self):
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
                PYTHON_ENABLE_DEBUG_LOGGING: "1"
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger1')
            resp = ctrl.send_request(req)

            self.assertEqual(resp.status_code, 200)
            container_log = ctrl.get_container_logs()
            func_start_idx = container_log.find(
                "Executing 'Functions.HttpTrigger1'")
            self.assertTrue(func_start_idx > -1)
            func_log = container_log[func_start_idx:]

            self.assertIn('logging info', func_log)
            self.assertIn('logging warning', func_log)
            self.assertIn('logging error', func_log)
            self.assertIn('logging debug', func_log)

    def test_pinning_functions_to_older_version(self):
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
                PYTHON_ISOLATE_WORKER_DEPENDENCIES: "1",
            })
            req = Request('GET', f'{ctrl.url}/api/HttpTrigger1')
            resp = ctrl.send_request(req)

            self.assertEqual(resp.status_code, 200)
            self.assertIn("Func Version: 1.11.1", resp.text)

    def test_opencensus_with_extensions_enabled(self):
        """A function app with extensions enabled containing the
         following libraries:

        azure-functions, opencensus

        should return 200 after importing all libraries.
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("Opencensus"),
                PYTHON_ENABLE_WORKER_EXTENSIONS: "1"
            })
            req = Request('GET', f'{ctrl.url}/api/opencensus')
            resp = ctrl.send_request(req)
            self.assertEqual(resp.status_code, 200)

    def test_opencensus_with_extensions_enabled_init_indexing(self):
        """
        A function app with init indexing enabled
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url("Opencensus"),
                PYTHON_ENABLE_WORKER_EXTENSIONS: "1",
                PYTHON_ENABLE_INIT_INDEXING: "true"
            })
            req = Request('GET', f'{ctrl.url}/api/opencensus')
            resp = ctrl.send_request(req)
            self.assertEqual(resp.status_code, 200)

    def test_reload_variables_after_oom_error(self):
        """
        A function app with HTTPtrigger mocking error code 137
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE": self._get_blob_url(
                    "OOMError"),
                PYTHON_ISOLATE_WORKER_DEPENDENCIES: "1"
            })
            req = Request('GET', f'{ctrl.url}/api/httptrigger')
            resp = ctrl.send_request(req)
            self.assertEqual(resp.status_code, 500)

            sleep(2)
            logs = ctrl.get_container_logs()
            self.assertRegex(
                logs,
                r"Applying prioritize_customer_dependencies: "
                r"worker_dependencies_path: \/azure-functions-host\/"
                r"workers\/python\/.*?\/LINUX\/X64,"
                r" customer_dependencies_path: \/home\/site\/wwwroot\/"
                r"\.python_packages\/lib\/site-packages, working_directory:"
                r" \/home\/site\/wwwroot, Linux Consumption: True,"
                r" Placeholder: False")

            self.assertNotIn("Failure Exception: ModuleNotFoundError",
                             logs)

    @skip("Flaky test.")
    def test_http_v2_fastapi_streaming_upload_download(self):
        """
        A function app using http v2 fastapi extension with streaming upload and
         download
        """
        with LinuxConsumptionWebHostController(_DEFAULT_HOST_VERSION,
                                               self._py_version) as ctrl:
            ctrl.assign_container(env={
                "AzureWebJobsStorage": self._storage,
                "SCM_RUN_FROM_PACKAGE":
                self._get_blob_url("HttpV2FastApiStreaming"),
                PYTHON_ENABLE_INIT_INDEXING: "true",
                PYTHON_ISOLATE_WORKER_DEPENDENCIES: "1"
            })

            def generate_random_bytes_stream():
                """Generate a stream of random bytes."""
                yield b'streaming'
                yield b'testing'
                yield b'response'
                yield b'is'
                yield b'returned'

            req = Request('POST',
                          f'{ctrl.url}/api/http_v2_fastapi_streaming',
                          data=generate_random_bytes_stream())
            resp = ctrl.send_request(req)
            self.assertEqual(resp.status_code, 200)

            streamed_data = b''
            for chunk in resp.iter_content(chunk_size=1024):
                if chunk:
                    streamed_data += chunk

            self.assertEqual(
                streamed_data, b'streamingtestingresponseisreturned')

    def _get_blob_url(self, scenario_name: str) -> str:
        base_url = "http://172.17.0.1:10000/devstoreaccount1/apps"

        container_sas_token = os.getenv('CONTAINER_SAS_TOKEN')
        if not container_sas_token:
            raise RuntimeError('Environment variable CONTAINER_SAS_TOKEN is '
                               'required before running Linux Consumption test')
        return f"{base_url}/{scenario_name}.zip?{container_sas_token}"
