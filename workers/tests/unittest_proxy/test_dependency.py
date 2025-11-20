import sys
import os
import unittest
from unittest.mock import patch

from proxy_worker.utils.dependency import DependencyManager
from tests.utils import testutils


class TestDependency(unittest.TestCase):

    @patch("proxy_worker.utils.dependency.DependencyManager._get_cx_deps_path",
           return_value="/mock/cx/site-packages")
    @patch("proxy_worker.utils.dependency.DependencyManager._get_cx_working_dir",
           return_value="/mock/cx")
    @patch("proxy_worker.utils.dependency.DependencyManager._get_worker_deps_path",
           return_value="/mock/worker")
    @patch("proxy_worker.utils.dependency.logger")
    def test_use_worker_dependencies(mock_logger, mock_worker, mock_cx_dir,
                                     mock_cx_deps):
        sys.path = ["/mock/cx/site-packages", "/mock/cx", "/original"]

        DependencyManager.initialize()
        DependencyManager.use_worker_dependencies()

        assert sys.path[0] == "/mock/worker"
        assert "/mock/cx/site-packages" not in sys.path
        assert "/mock/cx" not in sys.path

        mock_logger.info.assert_any_call(
            'Applying use_worker_dependencies:'
            ' worker_dependencies: %s,'
            ' customer_dependencies: %s,'
            ' working_directory: %s',
            "/mock/worker", "/mock/cx/site-packages", "/mock/cx"
        )

    @patch("proxy_worker.utils.dependency.DependencyManager._get_cx_deps_path",
           return_value="/mock/cx/site-packages")
    @patch("proxy_worker.utils.dependency.DependencyManager._get_worker_deps_path",
           return_value="/mock/worker")
    @patch("proxy_worker.utils.dependency.DependencyManager._get_cx_working_dir",
           return_value="/mock/cx")
    @patch("proxy_worker.utils.dependency.DependencyManager.is_in_linux_consumption",
           return_value=False)
    @patch("proxy_worker.utils.dependency.is_envvar_true", return_value=False)
    @patch("proxy_worker.utils.dependency.logger")
    def test_prioritize_customer_dependencies(mock_logger, mock_env, mock_linux,
                                              mock_cx_dir, mock_worker, mock_cx_deps):
        sys.path = ["/mock/worker", "/some/old/path"]

        DependencyManager.initialize()
        DependencyManager.prioritize_customer_dependencies("/override/cx")

        assert sys.path[0] == "/mock/cx/site-packages"
        assert sys.path[1] == "/mock/worker"
        expected_path = os.path.abspath("/override/cx")
        assert expected_path in sys.path

        assert any(
            "Finished prioritize_customer_dependencies" in str(call[0][0])
            for call in mock_logger.info.call_args_list
        )


class TestProtobufImports(unittest.TestCase):
    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_sys_path = patch('sys.path', [])
        self._patch_importer_cache = patch.dict('sys.path_importer_cache', {})
        self._patch_modules = patch.dict('sys.modules', {})
        self._customer_func_path = os.path.abspath(
            os.path.join(
                testutils.UNIT_TESTS_ROOT, 'resources', 'customer_func_path'
            )
        )
        self._worker_deps_path = os.path.abspath(
            os.path.join(
                testutils.UNIT_TESTS_ROOT, 'resources', 'worker_deps_path'
            )
        )
        self._customer_deps_path = os.path.abspath(
            os.path.join(
                testutils.UNIT_TESTS_ROOT, 'resources', 'customer_deps_path'
            )
        )

        self._patch_environ.start()
        self._patch_sys_path.start()
        self._patch_importer_cache.start()
        self._patch_modules.start()

    def tearDown(self):
        self._patch_environ.stop()
        self._patch_sys_path.stop()
        self._patch_importer_cache.stop()
        self._patch_modules.stop()
        DependencyManager.cx_deps_path = ''
        DependencyManager.cx_working_dir = ''
        DependencyManager.worker_deps_path = ''

    @unittest.skipIf(sys.version_info.minor != 13,
                     "The worker brings different protobuf versions"
                     "between 3.13 and 3.14.")
    def test_newrelic_protobuf_import_scenario_worker_deps_313(self):
        # https://github.com/Azure/azure-functions-python-worker/issues/1339
        # newrelic checks if protobuf has been imported and based on the
        # version it finds, imports a specific pb2 file.

        # protobuf is brought through the worker's deps.
        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = ""  # No customer deps
        DependencyManager.cx_working_dir = self._customer_func_path

        DependencyManager.prioritize_customer_dependencies()

        # protobuf v5 is found
        from google.protobuf import __version__

        protobuf_version = tuple(int(v) for v in __version__.split("."))
        self.assertIsNotNone(protobuf_version)
        self.assertEqual(protobuf_version[0], 5)

    @unittest.skipIf(sys.version_info.minor != 13,
                     "The worker brings different protobuf versions"
                     "between 3.13 and 3.14.")
    def test_newrelic_protobuf_import_scenario_user_deps_313(self):
        # https://github.com/Azure/azure-functions-python-worker/issues/1339
        # newrelic checks if protobuf has been imported and based on the
        # version it finds, imports a specific pb2 file.

        # protobuf is brought through the user's deps.
        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        DependencyManager.prioritize_customer_dependencies()

        # protobuf is found from worker deps, but newrelic won't find it
        from google.protobuf import __version__

        protobuf_version = tuple(int(v) for v in __version__.split("."))
        self.assertIsNotNone(protobuf_version)

        # newrelic tries to import protobuf v3
        self.assertEqual(protobuf_version[0], 3)

        # newrelic tries to import protobuf 5
        self.assertNotEqual(protobuf_version[0], 5)
