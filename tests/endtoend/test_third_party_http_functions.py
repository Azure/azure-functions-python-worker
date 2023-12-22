# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import requests

from tests.utils import testutils as utils
from tests.utils.testutils import E2E_TESTS_ROOT

HOST_JSON_TEMPLATE = """\
{
    "version": "2.0",
    "logging": {
        "logLevel": {
           "default": "Trace"
        }
    },
    "extensions": {
        "http": {
          "routePrefix": ""
        }
    },
    "functionTimeout": "00:05:00"
}
"""


class ThirdPartyHttpFunctionsTestBase:
    """Base test class containing common asgi/wsgi testcases, only testcases
    in classes extending TestThirdPartyHttpFunctions will by run"""

    class TestThirdPartyHttpFunctions(utils.WebHostTestCase):
        @classmethod
        def setUpClass(cls):
            host_json = cls.get_script_dir() / 'host.json'
            with open(host_json, 'w+') as f:
                f.write(HOST_JSON_TEMPLATE)
            super().setUpClass()

        @classmethod
        def tearDownClass(cls):
            super().tearDownClass()

        @classmethod
        def get_script_dir(cls):
            pass

        @classmethod
        def get_libraries_to_install(cls):
            libraries_required = ["flask", "fastapi"]
            return libraries_required

        @utils.retryable_test(3, 5)
        def test_function_index_page_should_return_undefined(self):
            root_url = self.webhost._addr
            r = requests.get(root_url)
            self.assertEqual(r.status_code, 404)

        @utils.retryable_test(3, 5)
        def test_get_endpoint_should_return_ok(self):
            """Test if the default template of Http trigger in Python
            Function app
            will return OK
            """
            r = self.webhost.request('GET', 'get_query_param', no_prefix=True)
            self.assertTrue(r.ok)
            self.assertEqual(r.text, "hello world")

        @utils.retryable_test(3, 5)
        def test_get_endpoint_should_accept_query_param(self):
            """Test if the azure.functions SDK is able to deserialize query
            parameter from the default template
            """
            r = self.webhost.request('GET', 'get_query_param',
                                     params={'name': 'dummy'}, no_prefix=True)
            self.assertTrue(r.ok)
            self.assertEqual(
                r.text,
                "hello dummy"
            )

        @utils.retryable_test(3, 5)
        def test_post_endpoint_should_accept_body(self):
            """Test if the azure.functions SDK is able to deserialize http body
            and pass it to default template
            """
            r = self.webhost.request('POST', 'post_str',
                                     data="dummy",
                                     headers={'content-type': 'text/plain'},
                                     no_prefix=True)
            self.assertTrue(r.ok)
            self.assertEqual(
                r.text,
                "hello dummy"
            )

        @utils.retryable_test(3, 5)
        def test_worker_status_endpoint_should_return_ok(self):
            """Test if the worker status endpoint will trigger
            _handle__worker_status_request and sends a worker status
            response back
            to host
            """
            root_url = self.webhost._addr
            health_check_url = f'{root_url}/admin/host/ping'
            r = requests.post(health_check_url,
                              params={'checkHealth': '1'})
            self.assertTrue(r.ok)

        @utils.retryable_test(3, 5)
        def test_worker_status_endpoint_should_return_ok_when_disabled(self):
            """Test if the worker status endpoint will trigger
            _handle__worker_status_request and sends a worker status
            response back
            to host
            """
            os.environ['WEBSITE_PING_METRICS_SCALE_ENABLED'] = '0'
            root_url = self.webhost._addr
            health_check_url = f'{root_url}/admin/host/ping'
            r = requests.post(health_check_url,
                              params={'checkHealth': '1'})
            self.assertTrue(r.ok)

        @utils.retryable_test(3, 5)
        def test_get_endpoint_should_accept_path_param(self):
            r = self.webhost.request('GET', 'get_path_param/1', no_prefix=True)
            self.assertTrue(r.ok)
            self.assertEqual(r.text, "hello 1")

        @utils.retryable_test(3, 5)
        def test_post_json_body_and_return_json_response(self):
            test_data = {
                "name": "apple",
                "description": "yummy"
            }
            r = self.webhost.request('POST', 'post_json_return_json_response',
                                     json=test_data,
                                     no_prefix=True)
            self.assertTrue(r.ok)
            self.assertEqual(r.json(), test_data)

        @utils.retryable_test(3, 5)
        def test_raise_exception_should_return_not_found(self):
            r = self.webhost.request('GET', 'raise_http_exception',
                                     no_prefix=True)
            self.assertEqual(r.status_code, 404)
            self.assertEqual(r.json(), {"detail": "Item not found"})


class TestAsgiHttpFunctions(
        ThirdPartyHttpFunctionsTestBase.TestThirdPartyHttpFunctions):
    @classmethod
    def get_script_dir(cls):
        return E2E_TESTS_ROOT / 'third_party_http_functions' / 'stein' / \
            'asgi_function'


class TestWsgiHttpFunctions(
        ThirdPartyHttpFunctionsTestBase.TestThirdPartyHttpFunctions):
    @classmethod
    def get_script_dir(cls):
        return E2E_TESTS_ROOT / 'third_party_http_functions' / 'stein' / \
            'wsgi_function'
