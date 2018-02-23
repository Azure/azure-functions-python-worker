import unittest

import azure.functions as azf
import azure.worker.type_impl as azw


class TestFunctions(unittest.TestCase):

    def test_http_request(self):
        r = azw.HttpRequest(
            'get',
            'http://example.com/abc?a=1',
            headers=dict(aaa='zzz', bAb='xYz'),
            params=dict(a='b'),
            body_type=azw.BindType.bytes,
            body=b'abc')

        self.assertEqual(r.method, 'GET')
        self.assertEqual(r.url, 'http://example.com/abc?a=1')
        self.assertEqual(r.params, {'a': 'b'})

        with self.assertRaises(TypeError):
            r.params['a'] = 'z'

        self.assertEqual(r.get_body(), b'abc')

        h = r.headers
        with self.assertRaises(AttributeError):
            r.headers = dict()

        self.assertEqual(h['aaa'], 'zzz')
        self.assertEqual(h['aaA'], 'zzz')
        self.assertEqual(h['bab'], 'xYz')
        self.assertEqual(h['BaB'], 'xYz')

        # test that request headers are read-only
        with self.assertRaises(TypeError):
            h['zzz'] = '123'

    def test_http_response(self):
        r = azf.HttpResponse(
            'body™',
            status_code=201,
            headers=dict(aaa='zzz', bAb='xYz'))

        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_body(), b'body\xe2\x84\xa2')

        self.assertEqual(r.mimetype, 'text/plain')
        self.assertEqual(r.charset, 'utf-8')

        h = r.headers
        with self.assertRaises(AttributeError):
            r.headers = dict()

        self.assertEqual(h['aaa'], 'zzz')
        self.assertEqual(h['aaA'], 'zzz')
        self.assertEqual(h['bab'], 'xYz')
        self.assertEqual(h['BaB'], 'xYz')

        # test that response headers are mutable
        h['zZz'] = '123'
        self.assertEqual(h['zzz'], '123')
