# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import os
import pathlib
import subprocess
import sys
import textwrap
from unittest import skipIf
from unittest.mock import Mock, patch

from azure.functions import Function
from azure.functions.decorators.retry_policy import RetryPolicy
from azure.functions.decorators.timer import TimerTrigger

from azure_functions_worker import functions
from azure_functions_worker.constants import PYTHON_SCRIPT_FILE_NAME, \
    PYTHON_SCRIPT_FILE_NAME_DEFAULT
from azure_functions_worker.loader import build_retry_protos
from tests.utils import testutils


class TestLoader(testutils.WebHostTestCase):

    def setUp(self) -> None:
        def test_function():
            return "Test"

        self.test_function = test_function
        self.func = Function(self.test_function, script_file="test.py")
        self.function_registry = functions.Registry()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'load_functions'

    def test_loader_building_fixed_retry_protos(self):
        trigger = TimerTrigger(schedule="*/1 * * * * *", arg_name="mytimer",
                               name="mytimer")
        self.func.add_trigger(trigger=trigger)
        setting = RetryPolicy(strategy="fixed_delay", max_retry_count="1",
                              delay_interval="00:02:00")
        self.func.add_setting(setting=setting)

        protos = build_retry_protos(self.func)
        self.assertEqual(protos.max_retry_count, 1)
        self.assertEqual(protos.retry_strategy, 1)  # 1 enum for fixed delay
        self.assertEqual(protos.delay_interval.seconds, 120)

    def test_loader_building_exponential_retry_protos(self):
        trigger = TimerTrigger(schedule="*/1 * * * * *", arg_name="mytimer",
                               name="mytimer")
        self.func.add_trigger(trigger=trigger)
        setting = RetryPolicy(strategy="exponential_backoff",
                              max_retry_count="1",
                              minimum_interval="00:01:00",
                              maximum_interval="00:02:00")
        self.func.add_setting(setting=setting)

        protos = build_retry_protos(self.func)
        self.assertEqual(protos.max_retry_count, 1)
        self.assertEqual(protos.retry_strategy,
                         0)  # 0 enum for exponential backoff
        self.assertEqual(protos.minimum_interval.seconds, 60)
        self.assertEqual(protos.maximum_interval.seconds, 120)

    @patch('azure_functions_worker.logging.logger.warning')
    def test_loader_retry_policy_attribute_error(self, mock_logger):
        self.func = Mock()
        self.func.get_settings_dict.side_effect = AttributeError('DummyError')

        result = build_retry_protos(self.func)
        self.assertIsNone(result)

        # Check if the logged message starts with the expected string
        logged_message = mock_logger.call_args[0][
            0]  # Get the first argument of the logger.warning call
        self.assertTrue(logged_message.startswith(
            'AttributeError while loading retry policy.'))

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


class TestPluginLoader(testutils.AsyncTestCase):

    @skipIf(sys.version_info.minor <= 7, "Skipping tests <= Python 3.7")
    async def test_entry_point_plugin(self):
        test_binding = pathlib.Path(__file__).parent / 'test-binding'
        subprocess.run([
            sys.executable, '-m', 'pip',
            '--disable-pip-version-check',
            'install', '--quiet',
            '-e', test_binding
        ], check=True)

        # This test must be run in a subprocess so that
        # pkg_resources picks up the newly installed package.
        code = textwrap.dedent('''
import asyncio
from azure_functions_worker import protos
from tests.utils import testutils

async def _runner():
    async with testutils.start_mockhost(
            script_root='unittests/test-binding/functions') as host:
        await host.init_worker()
        func_id, r = await host.load_function('foo')

        print(r.response.function_id == func_id)
        print(r.response.result.status == protos.StatusResult.Success)

asyncio.get_event_loop().run_until_complete(_runner())
''')

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, '-c', code,
                stdout=asyncio.subprocess.PIPE)

            stdout, stderr = await proc.communicate()

            # Trimming off carriage return charater when testing on Windows
            stdout_lines = [
                line.replace(b'\r', b'') for line in stdout.strip().split(b'\n')
            ]
            self.assertEqual(stdout_lines, [b'True', b'True'])

        finally:
            subprocess.run([
                sys.executable, '-m', 'pip',
                '--disable-pip-version-check',
                'uninstall', '-y', '--quiet', 'foo-binding'
            ], check=True)


class TestConfigurableFileName(testutils.WebHostTestCase):

    def setUp(self) -> None:
        def test_function():
            return "Test"

        self.file_name = PYTHON_SCRIPT_FILE_NAME_DEFAULT
        self.test_function = test_function
        self.func = Function(self.test_function, script_file="function_app.py")
        self.function_registry = functions.Registry()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'http_functions' / \
                                             'http_functions_stein'

    def test_correct_file_name(self):
        os.environ.update({PYTHON_SCRIPT_FILE_NAME: self.file_name})
        self.assertIsNotNone(os.environ.get(PYTHON_SCRIPT_FILE_NAME))
        self.assertEqual(os.environ.get(PYTHON_SCRIPT_FILE_NAME),
                         'function_app.py')
