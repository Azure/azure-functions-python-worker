import unittest

from azure import functions as azf
from azure.worker import type_impl


class TestFunctions(unittest.TestCase):

    def test_http_request_bytes(self):
        r = type_impl.HttpRequest(
            'get',
            'http://example.com/abc?a=1',
            headers=dict(aaa='zzz', bAb='xYz'),
            params=dict(a='b'),
            body_type=type_impl.TypedDataKind.bytes,
            body=b'abc')

        self.assertEqual(r.method, 'GET')
        self.assertEqual(r.url, 'http://example.com/abc?a=1')
        self.assertEqual(r.params, {'a': 'b'})

        with self.assertRaises(TypeError):
            r.params['a'] = 'z'

        self.assertEqual(r.get_body(), b'abc')

        with self.assertRaisesRegex(ValueError, 'does not have JSON'):
            r.get_json()

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

    def test_http_request_json(self):
        r = type_impl.HttpRequest(
            'POST',
            'http://example.com/abc?a=1',
            headers={},
            params={},
            body_type=type_impl.TypedDataKind.json,
            body='{"a":1}')

        self.assertEqual(r.method, 'POST')
        self.assertEqual(r.url, 'http://example.com/abc?a=1')
        self.assertEqual(r.params, {})

        self.assertEqual(r.get_body(), '{"a":1}')
        self.assertEqual(r.get_json(), {'a': 1})

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
