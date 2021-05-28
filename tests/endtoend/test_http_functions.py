# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
from unittest.mock import patch

import requests
from azure_functions_worker import testutils

REQUEST_TIMEOUT_SEC = 5


class TestHttpFunctions(testutils.WebHostTestCase):
    """Test the native Http Trigger in the local webhost.

    This test class will spawn a webhost from your <project_root>/build/webhost
    folder and replace the built-in Python with azure_functions_worker from
    your code base. Since the Http Trigger is a native suport from host, we
    don't need to setup any external resources.

    Compared to the unittests/test_http_functions.py, this file is more focus
    on testing the E2E flow scenarios.
    """
    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_environ.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    @testutils.retryable_test(3, 5)
    def test_function_index_page_should_return_ok(self):
        """The index page of Azure Functions should return OK in any
        circumstances
        """
        root_url = self.webhost._addr
        r = requests.get(root_url, timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_default_http_template_should_return_ok(self):
        """Test if the default template of Http trigger in Python Function app
        will return OK
        """
        r = self.webhost.request('GET', 'default_template',
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_default_http_template_should_accept_query_param(self):
        """Test if the azure.functions SDK is able to deserialize query
        parameter from the default template
        """
        r = self.webhost.request('GET', 'default_template',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query. This HTTP triggered function executed successfully.'
        )

    @testutils.retryable_test(3, 5)
    def test_default_http_template_should_accept_body(self):
        """Test if the azure.functions SDK is able to deserialize http body
        and pass it to default template
        """
        r = self.webhost.request('POST', 'default_template',
                                 data='{ "name": "body" }'.encode('utf-8'),
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, body. This HTTP triggered function executed successfully.'
        )

    @testutils.retryable_test(3, 5)
    def test_worker_status_endpoint_should_return_ok(self):
        """Test if the worker status endpoint will trigger
        _handle__worker_status_request and sends a worker status response back
        to host
        """
        root_url = self.webhost._addr
        health_check_url = f'{root_url}/admin/host/ping'
        r = requests.post(health_check_url,
                          params={'checkHealth': '1'},
                          timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    @testutils.retryable_test(3, 5)
    def test_worker_status_endpoint_should_return_ok_when_disabled(self):
        """Test if the worker status endpoint will trigger
        _handle__worker_status_request and sends a worker status response back
        to host
        """
        os.environ['WEBSITE_PING_METRICS_SCALE_ENABLED'] = '0'
        root_url = self.webhost._addr
        health_check_url = f'{root_url}/admin/host/ping'
        r = requests.post(health_check_url,
                          params={'checkHealth': '1'},
                          timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
