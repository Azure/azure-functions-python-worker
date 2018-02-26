from azure.worker import testutils


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
