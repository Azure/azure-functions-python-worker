# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time

from azure_functions_worker import testutils


class TestBlobFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blob_functions'

    @testutils.retryable_test(3, 5)
    def test_blob_io_str(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'get_blob_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

        r = self.webhost.request('GET', 'get_blob_as_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

    @testutils.retryable_test(3, 5)
    def test_blob_io_large_str(self):
        large_string = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB

        r = self.webhost.request('POST', 'put_blob_str', data=large_string)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'get_blob_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, large_string)

        r = self.webhost.request('GET', 'get_blob_as_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, large_string)

    @testutils.retryable_test(3, 5)
    def test_blob_io_bytes(self):
        r = self.webhost.request('POST', 'put_blob_bytes',
                                 data='test-dată'.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('POST', 'get_blob_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-dată')

        r = self.webhost.request('POST', 'get_blob_as_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-dată')

    @testutils.retryable_test(3, 5)
    def test_blob_io_large_bytes(self):
        large_string = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB

        r = self.webhost.request('POST', 'put_blob_bytes',
                                 data=large_string.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('POST', 'get_blob_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, large_string)

        r = self.webhost.request('POST', 'get_blob_as_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, large_string)

    @testutils.retryable_test(3, 5)
    def test_blob_io_filelike(self):
        r = self.webhost.request('POST', 'put_blob_filelike')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('POST', 'get_blob_filelike')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'filelike')

    @testutils.retryable_test(3, 5)
    def test_blob_io_return(self):
        r = self.webhost.request('POST', 'put_blob_return')
        self.assertEqual(r.status_code, 200)

        r = self.webhost.request('POST', 'get_blob_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'FROM RETURN')

    @testutils.retryable_test(3, 5)
    def test_blob_trigger(self):
        data = "DummyData"

        r = self.webhost.request('POST', 'put_blob_trigger',
                                 data=data.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Blob trigger may be processed after some delay
        # We check it every 2 seconds to allow the trigger to be fired
        max_retries = 10
        for try_no in range(max_retries):
            time.sleep(2)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_blob_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(
                    response,
                    {
                        'name': 'python-worker-tests/test-blob-trigger.txt',
                        'length': len(data),
                        'content': data
                    }
                )
                break
            except AssertionError:
                if try_no == max_retries - 1:
                    raise

    @testutils.retryable_test(3, 5)
    def test_blob_trigger_with_large_content(self):
        data = 'DummyDataDummyDataDummyData' * 1024 * 1024  # 27 MB

        r = self.webhost.request('POST', 'put_blob_trigger',
                                 data=data.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Blob trigger may be processed after some delay
        # We check it every 2 seconds to allow the trigger to be fired
        max_retries = 10
        for try_no in range(max_retries):
            time.sleep(2)

            try:
                # Check that the trigger has fired
                r = self.webhost.request('GET', 'get_blob_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(
                    response,
                    {
                        'name': 'python-worker-tests/test-blob-trigger.txt',
                        'length': len(data),
                        'content': data
                    }
                )
                break
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
