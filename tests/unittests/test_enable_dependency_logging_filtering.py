# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing
import os
from unittest.mock import patch
from tests.utils import testutils
from azure_functions_worker.constants import \
    PYTHON_ENABLE_DEPENDENCY_LOG_FILTERING_MODULES

HOST_JSON_TEMPLATE_WITH_LOGLEVEL_INFO = """\
{
    "version": "2.0",
    "logging": {
        "logLevel": {
           "default": "Information"
        }
    }
}
"""


class TestDependencyLoggingEnabledFunctions(testutils.WebHostTestCase):
    """
    Tests for cx dependency logging filtering enabled case.
    """

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        # Turn on feature flag
        os_environ[
            PYTHON_ENABLE_DEPENDENCY_LOG_FILTERING_MODULES] = 'function_app'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions' / \
            'dependency_logging_filter'

    def test_dependency_logging_filter_enabled(self):
        """
        Verify when cx dependency logging filter is enabled, cx function
        dependencies logs are not captured.
        """
        r = self.webhost.request('GET', 'default_template')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'ok')

    def check_log_dependency_logging_filter_enabled(self,
                                                    host_out: typing.List[
                                                        str]):
        self.assertIn('Python HTTP trigger function processed a request.',
                      host_out)
        self.assertNotIn('logging from external library', host_out)


class TestDependencyLoggingDisabledFunctions(testutils.WebHostTestCase):
    """
    Tests for cx dependency logging filtering disabled case.
    """

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        # Turn off feature flag
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions' / \
            'dependency_logging_filter'

    def test_dependency_logging_filter_disabled(self):
        """
        Verify when cx dependency logging filter is disabled, dependencies logs
        are captured.
        """
        r = self.webhost.request('GET', 'default_template')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'ok')

    def check_log_dependency_logging_filter_disabled(self,
                                                     host_out: typing.List[
                                                         str]):
        self.assertIn('Python HTTP trigger function processed a request.',
                      host_out)
        self.assertIn('logging from external library', host_out)


class TestDependencyLoggingEnabledBluePrintFunctions(testutils.WebHostTestCase):
    """
    Tests for cx dependency logging filtering with blueprint func enabled case.
    """

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        # Turn off feature flag
        os_environ[
            PYTHON_ENABLE_DEPENDENCY_LOG_FILTERING_MODULES] = 'function_app,' \
                                                              'blueprint'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions' / \
            'dependency_logging_filter'

    def test_dependency_logging_filter_blueprint_enabled(self):
        """
        Verify when cx dependency logging filter with blueprint func is
        enabled, dependencies logs
        are filtered out.
        """
        r = self.webhost.request('GET', 'test_blueprint_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'ok')

    def check_log_dependency_logging_filter_blueprint_enabled(self,
                                                              host_out:
                                                              typing.List[
                                                                  str]):
        self.assertIn('logging from blueprint',
                      host_out)
        self.assertNotIn('logging from external library', host_out)


class TestDependencyLoggingDisabledBluePrintFunctions(
        testutils.WebHostTestCase):
    """
    Tests for cx dependency logging filtering with blueprint func disabled
    case.
    """

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.UNIT_TESTS_FOLDER / 'log_filtering_functions' / \
            'dependency_logging_filter'

    def test_dependency_logging_filter_disabled_blueprint(self):
        """
        Verify when cx dependency logging filter with blueprint functions is
        disabled, dependencies logs are captured.
        """
        r = self.webhost.request('GET', 'test_blueprint_logging')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'ok')

    def check_log_dependency_logging_filter_disabled_blueprint(self,
                                                               host_out:
                                                               typing.List[
                                                                   str]):
        self.assertIn('logging from blueprint',
                      host_out)
        self.assertIn('logging from external library', host_out)
