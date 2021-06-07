# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import importlib.util
from unittest.case import skipIf
from unittest.mock import patch

from requests import Response
from azure_functions_worker import testutils
from azure_functions_worker.utils.common import is_envvar_true
from azure_functions_worker.constants import PYAZURE_INTEGRATION_TEST

REQUEST_TIMEOUT_SEC = 5


class TestDependencyFunctionsOnDedicated(testutils.WebHostTestCase):
    """Test the dependency manager E2E scneraio via Http Trigger.

    The following E2E tests ensures the dependency manager is behaving as
    expected. They are tested against the dependency_functions/ folder which
    contain a dummy .python_packages/ folder.
    """
    project_root = testutils.E2E_TESTS_ROOT / 'dependency_functions'
    customer_deps = project_root / '.python_packages' / 'lib' / 'site-packages'

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        # Turn on feature flag
        os_environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = '1'
        # Emulate Python worker in Azure enviroment.
        # For how the PYTHONPATH is set in Azure, check prodV3/worker.py.
        os_environ['PYTHONPATH'] = str(cls.customer_deps)

        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return cls.project_root

    @testutils.retryable_test(3, 5)
    def test_dependency_function_should_return_ok(self):
        """The common scenario of general import should return OK in any
        circumstances
        """
        r: Response = self.webhost.request('GET', 'report_dependencies')
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_feature_flag_is_turned_on(self):
        """Since passing the feature flag PYTHON_ISOLATE_WORKER_DEPENDENCIES to
        the host, the customer's function should also be able to receive it
        """
        r: Response = self.webhost.request('GET', 'report_dependencies')
        environments = r.json()['environments']
        flag_value = environments['PYTHON_ISOLATE_WORKER_DEPENDENCIES']
        self.assertEqual(flag_value, '1')

    @testutils.retryable_test(3, 5)
    def test_working_directory_resolution(self):
        """Check from the dependency manager and see if the current working
        directory is resolved correctly
        """
        r: Response = self.webhost.request('GET', 'report_dependencies')
        environments = r.json()['environments']

        dir = os.path.dirname(__file__)
        self.assertEqual(
            environments['AzureWebJobsScriptRoot'].lower(),
            os.path.join(dir, 'dependency_functions').lower()
        )

    @skipIf(
        is_envvar_true(PYAZURE_INTEGRATION_TEST),
        'Integration test expects dependencies derived from core tools folder'
    )
    @testutils.retryable_test(3, 5)
    def test_paths_resolution(self):
        """Dependency manager requires paths to be resolved correctly before
        switching to customer's modules. This test is to ensure when the app
        is in ready state, check if the paths are in good state.
        """
        r: Response = self.webhost.request('GET', 'report_dependencies')
        dm = r.json()['dependency_manager']
        self.assertEqual(
            dm['cx_working_dir'].lower(), str(self.project_root).lower()
        )
        self.assertEqual(
            dm['cx_deps_path'].lower(), str(self.customer_deps).lower()
        )

        # Should dervie the package location from the built-in azure.functions
        azf_spec = importlib.util.find_spec('azure.functions')
        self.assertEqual(
            dm['worker_deps_path'].lower(),
            os.path.abspath(
                os.path.join(os.path.dirname(azf_spec.origin), '..', '..')
            ).lower()
        )

    @testutils.retryable_test(3, 5)
    def test_loading_libraries_from_customers_package(self):
        """Since the Python now loaded the customer's dependencies, the
        libraries version should match the ones in .python_packages/ folder
        """
        r: Response = self.webhost.request('GET', 'report_dependencies')
        libraries = r.json()['libraries']

        self.assertEqual(
            libraries['proto.expected.version'], libraries['proto.version']
        )
        self.assertEqual(
            libraries['grpc.expected.version'], libraries['grpc.version']
        )
