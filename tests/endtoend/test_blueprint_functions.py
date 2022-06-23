# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
from unittest.mock import patch

import requests

from azure_functions_worker import testutils


class TestFunctionInBluePrintOnly(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
               'functions_in_blueprint_only'

    @testutils.retryable_test(3, 5)
    def test_function_in_blueprint_only(self):
        r = self.webhost.request('GET', 'default_template')
        self.assertTrue(r.ok)


class TestFunctionsInBothBlueprintAndFuncApp(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
               'functions_in_both_blueprint_functionapp'

    @testutils.retryable_test(3, 5)
    def test_functions_in_both_blueprint_functionapp(self):
        r = self.webhost.request('GET', 'default_template')
        self.assertTrue(r.ok)

        r = self.webhost.request('GET', 'return_http')
        self.assertTrue(r.ok)


class TestMultipleFunctionRegisters(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
               'multiple_function_registers'

    @testutils.retryable_test(3, 5)
    def test_function_in_blueprint_only(self):
        r = self.webhost.request('GET', 'return_http')
        self.assertEqual(r.status_code, 404)


class TestOnlyBlueprint(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
               'only_blueprint'

    @testutils.retryable_test(3, 5)
    def test_only_blueprint(self):
        """Test if the default template of Http trigger in Python
        Function app
        will return OK
        """
        r = self.webhost.request('GET', 'default_template')
        self.assertEqual(r.status_code, 404)
    #
    # @testutils.retryable_test(3, 5)
    # def test_default_http_template_should_accept_query_param(self):
    #     """Test if the azure.functions SDK is able to deserialize query
    #     parameter from the default template
    #     """
    #     r = self.webhost.request('GET', 'default_template',
    #                              params={'name': 'query'},
    #                              timeout=REQUEST_TIMEOUT_SEC)
    #     self.assertTrue(r.ok)
    #     self.assertEqual(
    #         r.content,
    #         b'Hello, query. This HTTP triggered function executed successfully.'
    #     )
    #
    # @testutils.retryable_test(3, 5)
    # def test_default_http_template_should_accept_body(self):
    #     """Test if the azure.functions SDK is able to deserialize http body
    #     and pass it to default template
    #     """
    #     r = self.webhost.request('POST', 'default_template',
    #                              data='{ "name": "body" }'.encode('utf-8'),
    #                              timeout=REQUEST_TIMEOUT_SEC)
    #     self.assertTrue(r.ok)
    #     self.assertEqual(
    #         r.content,
    #         b'Hello, body. This HTTP triggered function executed successfully.'
    #     )
    #
    # @testutils.retryable_test(3, 5)
    # def test_worker_status_endpoint_should_return_ok(self):
    #     """Test if the worker status endpoint will trigger
    #     _handle__worker_status_request and sends a worker status response back
    #     to host
    #     """
    #     root_url = self.webhost._addr
    #     health_check_url = f'{root_url}/admin/host/ping'
    #     r = requests.post(health_check_url,
    #                       params={'checkHealth': '1'},
    #                       timeout=REQUEST_TIMEOUT_SEC)
    #     self.assertTrue(r.ok)
    #
    # @testutils.retryable_test(3, 5)
    # def test_worker_status_endpoint_should_return_ok_when_disabled(self):
    #     """Test if the worker status endpoint will trigger
    #     _handle__worker_status_request and sends a worker status response back
    #     to host
    #     """
    #     os.environ['WEBSITE_PING_METRICS_SCALE_ENABLED'] = '0'
    #     root_url = self.webhost._addr
    #     health_check_url = f'{root_url}/admin/host/ping'
    #     r = requests.post(health_check_url,
    #                       params={'checkHealth': '1'},
    #                       timeout=REQUEST_TIMEOUT_SEC)
    #     self.assertTrue(r.ok)