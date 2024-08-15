# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from tests.utils import testutils


class TestLoader(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_ROOT / 'load_functions'

    def test_loader_simple(self):
        r = self.webhost.request('GET', 'simple')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.simple.main')

    def test_loader_custom_entrypoint(self):
        r = self.webhost.request('GET', 'entrypoint')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.entrypoint.main')

    def test_loader_no_script_file(self):
        r = self.webhost.request('GET', 'no_script_file')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.no_script_file.main')

    def test_loader_subdir(self):
        r = self.webhost.request('GET', 'subdir')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.subdir.sub.main')

    def test_loader_relimport(self):
        r = self.webhost.request('GET', 'relimport')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.relimport.relative')

    def test_loader_submodule(self):
        r = self.webhost.request('GET', 'submodule')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.submodule.sub_module.module')

    def test_loader_parentmodule(self):
        r = self.webhost.request('GET', 'parentmodule')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.parentmodule.module')

    def test_loader_absolute_thirdparty(self):
        """Allow third-party package import from .python_packages
        and worker_venv
        """

        r = self.webhost.request('GET', 'absolute_thirdparty')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'eh = azure.eventhub')

    def test_loader_prioritize_customer_module(self):
        """When a module in customer code has the same name with a third-party
        package, the worker should prioritize third-party package
        """

        r = self.webhost.request('GET', 'name_collision')
        self.assertEqual(r.status_code, 200)
        self.assertRegex(r.text, r'pt.__version__ = \d+.\d+.\d+')

    def test_loader_fix_customer_module_with_app_import(self):
        """When a module in customer code has the same name with a third-party
        package, if customer uses "import __app__.<module>" statement,
        the worker should load customer package
        """

        r = self.webhost.request('GET', 'name_collision_app_import')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'pt.__version__ = from.customer.code')

    def test_loader_implicit_import(self):
        """Since sys.path is now fixed with script root appended,
        implicit import statement is now acceptable.
        """

        r = self.webhost.request('GET', 'implicit_import')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 's_main = simple.main')

    def test_loader_module_not_found(self):
        """If a module cannot be found, should throw an exception with
        trouble shooting link https://aka.ms/functions-modulenotfound
        """
        r = self.webhost.request('GET', 'module_not_found')
        self.assertEqual(r.status_code, 500)

    def test_loader_init_should_only_invoke_outside_main_once(self):
        """Check if the code in __init__.py outside of main() function
        is only executed once
        """
        r = self.webhost.request('GET', 'outside_main_code_in_init')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'executed count = 1')

    def test_loader_main_should_only_invoke_outside_main_once(self):
        """Check if the code in main.py outside of main() function
        is only executed once
        """
        r = self.webhost.request('GET', 'outside_main_code_in_main')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'executed count = 1')

    def test_loader_outside_main_package_should_be_loaded_from_init(self):
        """Check if the package can still be loaded from __init__ module
        """
        r = self.webhost.request('GET', 'load_outside_main?from=init')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

    def test_loader_outside_main_package_should_be_loaded_from_package(self):
        """Check if the package can still be loaded from package
        """
        r = self.webhost.request('GET',
                                 'load_outside_main?from=package')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

    def check_log_loader_module_not_found(self, host_out):
        passed = False
        exception_message = "Exception: ModuleNotFoundError: "\
                            "No module named 'notfound'. "\
                            "Cannot find module. "\
                            "Please check the requirements.txt file for the "\
                            "missing module. For more info, please refer the "\
                            "troubleshooting guide: "\
                            "https://aka.ms/functions-modulenotfound. "\
                            "Current sys.path: "
        for log in host_out:
            if exception_message in log:
                passed = True
        self.assertTrue(passed)
