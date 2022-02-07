# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing

from azure_functions_worker import testutils
from azure_functions_worker.testutils import TESTS_ROOT, remove_path

HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO = """\
{
    "version": "2.0",
    "logging": {
        "logLevel": {
           "default": "Information"
        }
    },
    "functionTimeout": "00:05:00"
}
"""


class TestLogFilteringFunctions(testutils.WebHostTestCase):
    """This class is for testing the logger behavior in Python Worker when
    dealing with customer's log and system's log. Here's a list of expected
    behaviors:
                  local_console  customer_app_insight  functions_kusto_table
    system_log    false          false                 true
    customer_log  true           true                  false

    Please ensure the following unit test cases align with the expectations
    """

    @classmethod
    def setUpClass(cls):
        host_json = TESTS_ROOT / cls.get_script_dir() / 'host.json'

        with open(host_json, 'w+') as f:
            f.write(HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO)

        super(TestLogFilteringFunctions, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        host_json = TESTS_ROOT / cls.get_script_dir() / 'host.json'
        remove_path(host_json)

        super(TestLogFilteringFunctions, cls).tearDownClass()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions'

    def test_debug_logging(self):
        r = self.webhost.request('GET', 'debug_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-debug')

    def check_log_debug_logging(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging error', host_out)
        # See HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO, debug log is disabled
        self.assertNotIn('logging debug', host_out)

    def test_debug_with_user_logging(self):
        r = self.webhost.request('GET', 'debug_user_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-user-debug')

    def check_log_debug_with_user_logging(self, host_out: typing.List[str]):
        self.assertIn('logging info', host_out)
        self.assertIn('logging warning', host_out)
        self.assertIn('logging error', host_out)
        # See HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO, debug log is disabled
        self.assertNotIn('logging debug', host_out)

    def test_info_with_sdk_logging(self):
        """Invoke a HttpTrigger sdk_logging which contains logging invocation
        via the azure.functions logger. This should be treated as system logs,
        which means the log should not be displayed in local console.
        """
        r = self.webhost.request('GET', 'sdk_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-sdk-logger')

    def check_log_info_with_sdk_logging(self, host_out: typing.List[str]):
        # See TestLogFilteringFunctions docstring
        # System log should not be captured in console
        self.assertNotIn('sdk_logger info', host_out)
        self.assertNotIn('sdk_logger warning', host_out)
        self.assertNotIn('sdk_logger error', host_out)
        self.assertNotIn('sdk_logger debug', host_out)

    def test_info_with_sdk_submodule_logging(self):
        """Invoke a HttpTrigger sdk_submodule_logging which contains logging
        invocation via the azure.functions logger. This should be treated as
        system logs.
        """
        r = self.webhost.request('GET', 'sdk_submodule_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK-sdk-submodule-logging')

    def check_log_info_with_sdk_submodule_logging(self,
                                                  host_out: typing.List[str]):
        # See TestLogFilteringFunctions docstring
        # System log should not be captured in console
        self.assertNotIn('sdk_submodule_logger info', host_out)
        self.assertNotIn('sdk_submodule_logger warning', host_out)
        self.assertNotIn('sdk_submodule_logger error', host_out)
        self.assertNotIn('sdk_submodule_logger debug', host_out)
