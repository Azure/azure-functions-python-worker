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
        r = self.webhost.request('GET', 'str_return')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'Hello World!')

    def test_get_method_request(self):
        r = self.webhost.request(
            'GET', 'str_return_req_json',
            params={'a': 1, 'b': ':%)'},
            headers={'xxx': 'zzz'})

        self.assertEqual(r.status_code, 200)

        req = r.json()

        self.assertEqual(req['method'], 'GET')
        self.assertEqual(req['params'], {'a': '1', 'b': ':%)'})
        self.assertEqual(req['headers']['xxx'], 'zzz')

        self.assertIn('str_return_req_json', req['url'])

    def test_post_method_request(self):
        r = self.webhost.request(
            'POST', 'str_return_req_json',
            params={'a': 1, 'b': ':%)'},
            headers={'xxx': 'zzz'},
            data={'key': 'value'})

        self.assertEqual(r.status_code, 200)

        req = r.json()

        self.assertEqual(req['method'], 'POST')
        self.assertEqual(req['params'], {'a': '1', 'b': ':%)'})
        self.assertEqual(req['headers']['xxx'], 'zzz')

        self.assertIn('str_return_req_json', req['url'])

        self.assertEqual(req['get_body'], 'key=value')
