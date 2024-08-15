# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import pathlib
import subprocess
import sys
import textwrap
import unittest
from unittest import skipIf
from unittest.mock import Mock, patch

from azure.functions import Function
from azure.functions.decorators.retry_policy import RetryPolicy
from azure.functions.decorators.timer import TimerTrigger
from tests.utils import testutils

from azure_functions_worker import functions
from azure_functions_worker.loader import build_retry_protos


class TestLoader(unittest.TestCase):

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
