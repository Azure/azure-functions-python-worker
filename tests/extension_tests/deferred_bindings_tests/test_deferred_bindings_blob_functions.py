# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time
import unittest
import sys

from tests.utils import testutils


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsBlobFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EXTENSION_TESTS_FOLDER / 'deferred_bindings_tests' / \
            'deferred_bindings_blob_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azurefunctions-extensions-bindings-blob']

    def test_blob_str(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        time.sleep(5)

        r = self.webhost.request('GET', 'get_bc_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

        r = self.webhost.request('GET', 'get_cc_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

        r = self.webhost.request('GET', 'get_ssd_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

    def test_blob_bytes(self):
        r = self.webhost.request('POST', 'put_blob_bytes',
                                 data='test-dată'.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        time.sleep(5)

        r = self.webhost.request('POST', 'get_bc_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-dată')

        r = self.webhost.request('POST', 'get_cc_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-dată')

        r = self.webhost.request('POST', 'get_ssd_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-dată')

    def test_bc_blob_trigger(self):
        data = "DummyData"

        r = self.webhost.request('POST', 'put_bc_trigger',
                                 data=data.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Blob trigger may be processed after some delay
        # We check it every 2 seconds to allow the trigger to be fired
        max_retries = 10
        for try_no in range(max_retries):
            time.sleep(5)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_bc_blob_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(response['name'],
                                 'test-blobclient-trigger.txt')
                self.assertEqual(response['content'], data)

                break
            except AssertionError:
                if try_no == max_retries - 1:
                    raise

    def test_cc_blob_trigger(self):
        data = "DummyData"

        r = self.webhost.request('POST', 'put_cc_trigger',
                                 data=data.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Blob trigger may be processed after some delay
        # We check it every 2 seconds to allow the trigger to be fired
        max_retries = 10
        for try_no in range(max_retries):
            time.sleep(5)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_cc_blob_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(response['name'],
                                 'python-worker-tests')
                self.assertEqual(response['content'], data)

                break
            except AssertionError:
                if try_no == max_retries - 1:
                    raise

    def test_ssd_blob_trigger(self):
        data = "DummyData"

        r = self.webhost.request('POST', 'put_ssd_trigger',
                                 data=data.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Blob trigger may be processed after some delay
        # We check it every 2 seconds to allow the trigger to be fired
        max_retries = 10
        for try_no in range(max_retries):
            time.sleep(5)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_ssd_blob_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(response['content'], data)

                break
            except AssertionError:
                if try_no == max_retries - 1:
                    raise

    def test_bc_and_inputstream_input(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'bc_and_inputstream_input')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data - input stream test-data - blob client')

    def test_inputstream_and_bc_input(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'inputstream_and_bc_input')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data - input stream test-data - blob client')

    def test_type_undefined(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'type_undefined')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

    def test_caching(self):
        '''
        The cache returns the same type based on resource and function name.
        Two different functions with clients that access the same resource
        will have two different clients. This tests that the same client
        is returned for each invocation and that the clients are different
        between the two functions.
        '''

        r = self.webhost.request('GET', 'blob_cache')
        r2 = self.webhost.request('GET', 'blob_cache2')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        client = r.text
        client2 = r2.text
        self.assertNotEqual(client, client2)

        r = self.webhost.request('GET', 'blob_cache')
        r2 = self.webhost.request('GET', 'blob_cache2')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r.text, client)
        self.assertEqual(r2.text, client2)
        self.assertNotEqual(r.text, r2.text)

        r = self.webhost.request('GET', 'blob_cache')
        r2 = self.webhost.request('GET', 'blob_cache2')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r.text, client)
        self.assertEqual(r2.text, client2)
        self.assertNotEqual(r.text, r2.text)

    def test_failed_client_creation(self):
        r = self.webhost.request('GET', 'invalid_connection_info')
        # Without the http_v2_enabled default definition, this request would time out.
        # Instead, it fails immediately
        self.assertEqual(r.status_code, 500)
