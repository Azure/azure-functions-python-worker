# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
import unittest
from unittest.mock import patch

from azure_functions_worker import testutils
from azure_functions_worker.utils.dependency import DependencyManager


class TestDependencyManager(unittest.TestCase):

    def setUp(self):
        self._patch_environ = patch.dict('os.environ', {})
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

    def test_should_not_have_any_paths_initially(self):
        self.assertEqual(DependencyManager.cx_deps_path, '')
        self.assertEqual(DependencyManager.cx_working_dir, '')
        self.assertEqual(DependencyManager.worker_deps_path, '')

    def test_initialize_in_linux_consumption(self):
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'
        sys.path.extend([
            '/tmp/functions\\standby\\wwwroot',
            '/home/site/wwwroot/.python_packages/lib/site-packages',
            '/azure-functions-host/workers/python/3.6/LINUX/X64',
            '/home/site/wwwroot'
        ])
        DependencyManager.initialize()
        self.assertEqual(
            DependencyManager.cx_deps_path,
            '/home/site/wwwroot/.python_packages/lib/site-packages'
        )
        self.assertEqual(
            DependencyManager.cx_working_dir,
            '/home/site/wwwroot',
        )
        self.assertEqual(
            DependencyManager.worker_deps_path,
            '/azure-functions-host/workers/python/3.6/LINUX/X64'
        )

    def test_initialize_in_linux_dedicated(self):
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'
        sys.path.extend([
            '/home/site/wwwroot',
            '/home/site/wwwroot/.python_packages/lib/site-packages',
            '/azure-functions-host/workers/python/3.7/LINUX/X64'
        ])
        DependencyManager.initialize()
        self.assertEqual(
            DependencyManager.cx_deps_path,
            '/home/site/wwwroot/.python_packages/lib/site-packages'
        )
        self.assertEqual(
            DependencyManager.cx_working_dir,
            '/home/site/wwwroot',
        )
        self.assertEqual(
            DependencyManager.worker_deps_path,
            '/azure-functions-host/workers/python/3.7/LINUX/X64'
        )

    def test_initialize_in_windows_core_tools(self):
        os.environ['AzureWebJobsScriptRoot'] = 'C:\\FunctionApp'
        sys.path.extend([
            'C:\\Users\\hazeng\\AppData\\Roaming\\npm\\'
            'node_modules\\azure-functions-core-tools\\bin\\'
            'workers\\python\\3.6\\WINDOWS\\X64',
            'C:\\FunctionApp\\.venv38\\lib\\site-packages',
            'C:\\FunctionApp'
        ])
        DependencyManager.initialize()
        self.assertEqual(
            DependencyManager.cx_deps_path,
            'C:\\FunctionApp\\.venv38\\lib\\site-packages'
        )
        self.assertEqual(
            DependencyManager.cx_working_dir,
            'C:\\FunctionApp',
        )
        self.assertEqual(
            DependencyManager.worker_deps_path,
            'C:\\Users\\hazeng\\AppData\\Roaming\\npm\\node_modules\\'
            'azure-functions-core-tools\\bin\\workers\\python\\3.6\\WINDOWS'
            '\\X64'
        )

    def test_get_cx_deps_path_in_no_script_root(self):
        result = DependencyManager._get_cx_deps_path()
        self.assertEqual(result, '')

    def test_get_cx_deps_path_in_script_root_no_sys_path(self):
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'
        result = DependencyManager._get_cx_deps_path()
        self.assertEqual(result, '')

    def test_get_cx_deps_path_in_script_root_with_sys_path_linux_py36(self):
        # Test for Python 3.6 Azure Environment
        sys.path.append('/home/site/wwwroot/.python_packages/sites/lib/'
                        'python3.6/site-packages/')
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'
        result = DependencyManager._get_cx_deps_path()
        self.assertEqual(result, '/home/site/wwwroot/.python_packages/sites/'
                         'lib/python3.6/site-packages/')

    def test_get_cx_deps_path_in_script_root_with_sys_path_linux(self):
        # Test for Python 3.7+ Azure Environment
        sys.path.append('/home/site/wwwroot/.python_packages/sites/lib/'
                        'site-packages/')
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'
        result = DependencyManager._get_cx_deps_path()
        self.assertEqual(result, '/home/site/wwwroot/.python_packages/sites/'
                         'lib/site-packages/')

    def test_get_cx_deps_path_in_script_root_with_sys_path_windows(self):
        # Test for Windows Core Tools Environment
        sys.path.append('C:\\FunctionApp\\sites\\lib\\site-packages')
        os.environ['AzureWebJobsScriptRoot'] = 'C:\\FunctionApp'
        result = DependencyManager._get_cx_deps_path()
        self.assertEqual(result,
                         'C:\\FunctionApp\\sites\\lib\\site-packages')

    def test_get_cx_working_dir_no_script_root(self):
        result = DependencyManager._get_cx_working_dir()
        self.assertEqual(result, '')

    def test_get_cx_working_dir_with_script_root_linux(self):
        # Test for Azure Environment
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'
        result = DependencyManager._get_cx_working_dir()
        self.assertEqual(result, '/home/site/wwwroot')

    def test_get_cx_working_dir_with_script_root_windows(self):
        # Test for Windows Core Tools Environment
        os.environ['AzureWebJobsScriptRoot'] = 'C:\\FunctionApp'
        result = DependencyManager._get_cx_working_dir()
        self.assertEqual(result, 'C:\\FunctionApp')

    def test_get_worker_deps_path_with_no_worker_sys_path(self):
        result = DependencyManager._get_worker_deps_path()
        worker_parent = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..')
        )
        self.assertEqual(result.lower(), worker_parent.lower())

    def test_get_worker_deps_path_from_windows_core_tools(self):
        # Test for Windows Core Tools Environment
        sys.path.append('C:\\Users\\hazeng\\AppData\\Roaming\\npm\\'
                        'node_modules\\azure-functions-core-tools\\bin\\'
                        'workers\\python\\3.6\\WINDOWS\\X64')
        result = DependencyManager._get_worker_deps_path()
        self.assertEqual(result,
                         'C:\\Users\\hazeng\\AppData\\Roaming\\npm\\'
                         'node_modules\\azure-functions-core-tools\\bin\\'
                         'workers\\python\\3.6\\WINDOWS\\X64')

    def test_get_worker_deps_path_from_linux_azure_environment(self):
        # Test for Azure Environment
        sys.path.append('/azure-functions-host/workers/python/3.7/LINUX/X64')
        result = DependencyManager._get_worker_deps_path()
        self.assertEqual(result,
                         '/azure-functions-host/workers/python/3.7/LINUX/X64')

    def test_get_worker_deps_path_without_worker_path(self):
        # Test when worker path is not provided
        sys.path.append('/home/site/wwwroot')
        result = DependencyManager._get_worker_deps_path()
        worker_parent = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..')
        )
        self.assertEqual(result.lower(), worker_parent.lower())

    def test_add_to_sys_path_add_to_first(self):
        DependencyManager._add_to_sys_path(self._customer_deps_path, True)
        self.assertEqual(sys.path[0], self._customer_deps_path)

    def test_add_to_sys_path_add_to_last(self):
        DependencyManager._add_to_sys_path(self._customer_deps_path, False)
        self.assertEqual(sys.path[-1], self._customer_deps_path)

    def test_add_to_sys_path_no_duplication(self):
        DependencyManager._add_to_sys_path(self._customer_deps_path, True)
        DependencyManager._add_to_sys_path(self._customer_deps_path, True)
        path_count = len(list(filter(
            lambda x: x == self._customer_deps_path, sys.path
        )))
        self.assertEqual(path_count, 1)

    def test_add_to_sys_path_import_module(self):
        DependencyManager._add_to_sys_path(self._customer_deps_path, True)
        import common_module # NoQA
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

    def test_add_to_sys_path_importer_cache(self):
        DependencyManager._add_to_sys_path(self._customer_deps_path, True)
        import common_module  # NoQA
        self.assertIn(self._customer_deps_path, sys.path_importer_cache)

    def test_add_to_sys_path_importer_cache_reloaded(self):
        # First import the common module from worker_deps_path
        DependencyManager._add_to_sys_path(self._worker_deps_path, True)
        import common_module  # NoQA
        self.assertIn(self._worker_deps_path, sys.path_importer_cache)
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._worker_deps_path, 'common_module')
        )

        # Mock that the customer's script are running in a different module
        # (e.g. HttpTrigger/__init__.py)
        del sys.modules['common_module']
        del common_module

        # Import the common module from customer_deps_path
        # Customer should only see their own module
        DependencyManager._add_to_sys_path(self._customer_deps_path, True)
        import common_module  # NoQA
        self.assertIn(self._customer_deps_path, sys.path_importer_cache)
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

    def test_reload_all_namespaces_from_customer_deps(self):
        """The test simulates a linux consumption environment where the worker
        transits from placeholder mode to specialized worker with customer's
        dependencies. First the worker will use worker's dependencies for its
        own modules. After worker init request, it starts adding customer's
        library path into sys.path (e.g. .python_packages/). The final step
        is in environment reload where the worker is fully specialized,
        reloading all libraries from customer's package.
        """
        # Setup app settings
        os.environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = 'true'
        os.environ['AzureWebJobsScriptRoot'] = '/home/site/wwwroot'

        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path

        # Ensure the common_module is imported from _worker_deps_path
        DependencyManager.use_worker_dependencies()
        import common_module  # NoQA
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._worker_deps_path, 'common_module')
        )

        # At worker init request
        DependencyManager.prioritize_customer_dependencies()

        # At placeholder specialization from function_environment_reload
        DependencyManager.reload_all_namespaces_from_customer_deps(
            self._customer_func_path
        )
        del common_module

        # Now the module should be imported from customer dependency
        import common_module  # NoQA
        self.assertIn(self._customer_deps_path, sys.path_importer_cache)
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

        # The worker dependency path remains as the last entry in sys.path
        self.assertEqual(sys.path[-1], self._worker_deps_path)

    def test_remove_from_sys_path(self):
        sys.path.append(self._customer_deps_path)
        DependencyManager._remove_from_sys_path(self._customer_deps_path)
        self.assertNotIn(self._customer_deps_path, sys.path)

    def test_remove_from_sys_path_should_remove_all_duplications(self):
        sys.path.insert(0, self._customer_deps_path)
        sys.path.append(self._customer_deps_path)
        DependencyManager._remove_from_sys_path(self._customer_deps_path)
        self.assertNotIn(self._customer_deps_path, sys.path)

    def test_remove_from_sys_path_should_remove_path_importer_cache(self):
        # Import a common_module from customer deps will create a path finter
        # cache in sys.path_importer_cache
        sys.path.insert(0, self._customer_deps_path)
        import common_module  # NoQA
        self.assertIn(self._customer_deps_path, sys.path_importer_cache)

        # Remove sys.path_importer_cache
        DependencyManager._remove_from_sys_path(self._customer_deps_path)
        self.assertNotIn(self._customer_deps_path, sys.path_importer_cache)

    def test_remove_from_sys_path_should_remove_related_module(self):
        # Import a common_module from customer deps will create a module import
        # cache in sys.module
        sys.path.insert(0, self._customer_deps_path)
        import common_module  # NoQA
        self.assertIn('common_module', sys.modules)

        # Remove sys.path_importer_cache
        DependencyManager._remove_from_sys_path(self._customer_deps_path)
        self.assertNotIn('common_module', sys.modules)

    def test_clear_path_importer_cache_and_modules(self):
        # Ensure sys.path_importer_cache and sys.modules cache is cleared
        sys.path.insert(0, self._customer_deps_path)
        import common_module  # NoQA
        self.assertIn('common_module', sys.modules)

        # Clear out cache
        DependencyManager._clear_path_importer_cache_and_modules(
            self._customer_deps_path
        )

        # Ensure cache is cleared
        self.assertNotIn('common_module', sys.modules)

    def test_clear_path_importer_cache_and_modules_reimport(self):
        # First import common_module from _customer_deps_path
        sys.path.insert(0, self._customer_deps_path)
        import common_module  # NoQA
        self.assertIn('common_module', sys.modules)
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

        # Clean up cache
        DependencyManager._clear_path_importer_cache_and_modules(
            self._customer_deps_path
        )
        self.assertNotIn('common_module', sys.modules)

        # Clean up namespace
        del common_module

        # Try import common_module from _worker_deps_path
        sys.path.insert(0, self._worker_deps_path)

        # Ensure new import is from _worker_deps_path
        import common_module  # NoQA
        self.assertIn('common_module', sys.modules)
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._worker_deps_path, 'common_module')
        )

    def test_clear_path_importer_cache_and_modules_retain_namespace(self):
        # First import common_module from _customer_deps_path as customer_mod
        sys.path.insert(0, self._customer_deps_path)
        import common_module as customer_mod  # NoQA
        self.assertIn('common_module', sys.modules)
        self.assertEqual(
            customer_mod.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

        # Clean up cache
        DependencyManager._clear_path_importer_cache_and_modules(
            self._customer_deps_path
        )
        self.assertNotIn('common_module', sys.modules)

        # Try import common_module from _worker_deps_path as worker_mod
        sys.path.insert(0, self._worker_deps_path)

        # Ensure new import is from _worker_deps_path
        import common_module as worker_mod # NoQA
        self.assertIn('common_module', sys.modules)
        self.assertEqual(
            worker_mod.package_location,
            os.path.join(self._worker_deps_path, 'common_module')
        )

    def test_use_worker_dependencies(self):
        # Setup app settings
        os.environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = 'true'

        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the common_module is imported from _worker_deps_path
        DependencyManager.use_worker_dependencies()
        import common_module  # NoQA
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._worker_deps_path, 'common_module')
        )

    def test_use_worker_dependencies_disable(self):
        # Setup app settings
        os.environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = 'false'

        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # The common_module cannot be imported since feature is disabled
        DependencyManager.use_worker_dependencies()
        with self.assertRaises(ImportError):
            import common_module  # NoQA

    @unittest.skipUnless(
        sys.version_info.major == 3 and sys.version_info.minor in (6, 7, 8),
        'Test only available for Python 3.6, 3.7, or 3.8'
    )
    def test_use_worker_dependencies_default_python_36_37_38(self):
        # Feature should be disabled in Python 3.6, 3.7, and 3.8
        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # The common_module cannot be imported since feature is disabled
        DependencyManager.use_worker_dependencies()
        with self.assertRaises(ImportError):
            import common_module  # NoQA

    @unittest.skip(
        'Test is not available due to feature flag is turned off'
    )
    def test_use_worker_dependencies_default_python_39(self):
        # Feature should be enabled in Python 3.9 by default
        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the common_module is imported from _worker_deps_path
        DependencyManager.use_worker_dependencies()
        import common_module  # NoQA
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._worker_deps_path, 'common_module')
        )

    def test_prioritize_customer_dependencies(self):
        # Setup app settings
        os.environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = 'true'

        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the common_module is imported from _customer_deps_path
        DependencyManager.prioritize_customer_dependencies()
        import common_module  # NoQA
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

        # The worker path should be the last in the sys.path
        self.assertEqual(sys.path[-1], self._worker_deps_path)

    def test_prioritize_customer_dependencies_disable(self):
        # Setup app settings
        os.environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = 'false'

        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the common_module is imported from _customer_deps_path
        DependencyManager.prioritize_customer_dependencies()
        with self.assertRaises(ImportError):
            import common_module  # NoQA

    @unittest.skipUnless(
        sys.version_info.major == 3 and sys.version_info.minor in (6, 7, 8),
        'Test only available for Python 3.6, 3.7, or 3.8'
    )
    def test_prioritize_customer_dependencies_default_python_36_37_38(self):
        # Feature should be disabled in Python 3.6, 3.7, and 3.8
        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the common_module is imported from _customer_deps_path
        DependencyManager.prioritize_customer_dependencies()
        with self.assertRaises(ImportError):
            import common_module  # NoQA

    @unittest.skip(
        'Test is not available since feature flag is turned off'
    )
    def test_prioritize_customer_dependencies_default_python_39(self):
        # Feature should be enabled in Python 3.9 by default
        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the common_module is imported from _customer_deps_path
        DependencyManager.prioritize_customer_dependencies()
        import common_module  # NoQA
        self.assertEqual(
            common_module.package_location,
            os.path.join(self._customer_deps_path, 'common_module')
        )

    def test_prioritize_customer_dependencies_from_working_directory(self):
        # Setup app settings
        os.environ['PYTHON_ISOLATE_WORKER_DEPENDENCIES'] = 'true'

        # Setup paths
        DependencyManager.worker_deps_path = self._worker_deps_path
        DependencyManager.cx_deps_path = self._customer_deps_path
        DependencyManager.cx_working_dir = self._customer_func_path

        # Ensure the func_specific_module is imported from _customer_func_path
        DependencyManager.prioritize_customer_dependencies()
        import func_specific_module  # NoQA
        self.assertEqual(
            func_specific_module.package_location,
            os.path.join(self._customer_func_path, 'func_specific_module')
        )

    def test_remove_module_cache(self):
        # First import the common_module and create a sys.modules cache
        sys.path.append(self._customer_deps_path)
        import common_module  # NoQA
        self.assertIn('common_module', sys.modules)

        # Ensure the module cache will be remove
        DependencyManager._remove_module_cache(self._customer_deps_path)
        self.assertNotIn('common_module', sys.modules)

    def test_remove_module_cache_with_namespace_remain(self):
        # Create common_module namespace
        sys.path.append(self._customer_deps_path)
        import common_module  # NoQA

        # Ensure namespace remains after module cache is removed
        DependencyManager._remove_module_cache(self._customer_deps_path)
        self.assertIsNotNone(common_module)
