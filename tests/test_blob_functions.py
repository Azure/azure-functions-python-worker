import time

from azure.functions_worker import testutils


class TestBlobFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'blob_functions'

    def test_blob_io_str(self):
        r = self.webhost.request('POST', 'put_blob_str', data='test-data')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('GET', 'get_blob_str')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-data')

    def test_blob_io_bytes(self):
        r = self.webhost.request('POST', 'put_blob_bytes',
                                 data='test-dată'.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('POST', 'get_blob_bytes')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'test-dată')

    def test_blob_io_filelike(self):
        r = self.webhost.request('POST', 'put_blob_filelike')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        r = self.webhost.request('POST', 'get_blob_filelike')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'filelike')

    def test_blob_io_return(self):
        r = self.webhost.request('POST', 'put_blob_return')
        self.assertEqual(r.status_code, 200)

        r = self.webhost.request('POST', 'get_blob_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'FROM RETURN')

    def test_blob_trigger(self):
        data = str(round(time.time()))

        r = self.webhost.request('POST', 'put_blob_trigger',
                                 data=data.encode('utf-8'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire
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
                        'length': 10,
                        'content': data
                    }
                )
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
