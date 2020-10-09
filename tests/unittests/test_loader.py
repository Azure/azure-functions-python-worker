# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import pathlib
import subprocess
import sys
import textwrap

from azure_functions_worker import testutils


class TestLoader(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'load_functions'

    def test_loader_simple(self):
        r = self.webhost.request('GET', 'simple')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.simple.main')

    def test_loader_custom_entrypoint(self):
        r = self.webhost.request('GET', 'entrypoint')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '__app__.entrypoint.main')

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

    def check_log_loader_module_not_found(self, host_out):
        self.assertIn("Exception: ModuleNotFoundError: "
                      "No module named 'notfound'. "
                      "Troubleshooting Guide: "
                      "https://aka.ms/functions-modulenotfound", host_out)


class TestPluginLoader(testutils.AsyncTestCase):

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
from azure_functions_worker import testutils

async def _runner():
    async with testutils.start_mockhost(
            script_root='unittests/test-binding/functions') as host:
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
