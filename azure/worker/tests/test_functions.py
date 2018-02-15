import unittest

from azure.worker import testutils


class TestFunctions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.webhost = testutils.start_webhost()

    @classmethod
    def tearDownClass(cls):
        cls.webhost.stop()
        cls.webhost = None

    def test_str_return(self):
        r = self.webhost.get_request('str_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello World!')
