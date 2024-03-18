# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time

from tests.utils import testutils
from azure_functions_worker.bindings import meta


class TestSdkBlobFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'deferred_bindings_functions' / \
            "blob_functions"

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

    def test_type_undefined(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'type_undefined')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

        self.assertFalse(meta.deferred_bindings_enabled)

    def test_caching(self):
        # Cache is empty at the start
        self.assertEqual(meta.SDK_CACHE, {})
        r = self.webhost.request('GET', 'blob_cache')
        self.assertEqual(r.status_code, 200)
