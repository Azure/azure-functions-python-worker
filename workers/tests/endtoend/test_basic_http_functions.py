# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from tests.utils import testutils

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
        super().setUp()

    def tearDown(self):
        super().tearDown()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    def test_function_index_page_should_return_ok(self):
        """The index page of Azure Functions should return OK in any
        circumstances
        """
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

    def test_default_http_template_should_return_ok(self):
        """Test if the default template of Http trigger in Python Function app
        will return OK
        """
        r = self.webhost.request('GET', 'default_template',
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)

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


class TestHttpFunctionsStein(TestHttpFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein'

    def test_return_custom_class(self):
        """Test if returning a custom class returns OK
        """
        r = self.webhost.request('GET', 'custom_response',
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertEqual(
            r.content,
            b'{"status": "healthy"}'
        )
        self.assertTrue(r.ok)

    def test_return_custom_class_with_query_param(self):
        """Test if query is accepted
        """
        r = self.webhost.request('GET', 'custom_response',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'{"name": "query"}'
        )


class TestHttpFunctionsSteinGeneric(TestHttpFunctionsStein):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
                                            'http_functions_stein' / \
                                            'generic'
