# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import unittest

from azure import functions as azf
from azure.functions import http as bind_http
from azure.functions import meta as bind_meta


class TestFunctions(unittest.TestCase):

    def test_http_request_bytes(self):
        r = bind_http.HttpRequest(
            'get',
            'http://example.com/abc?a=1',
            headers=dict(aaa='zzz', bAb='xYz'),
            params=dict(a='b'),
            route_params={'route': 'param'},
            body_type='bytes',
            body=b'abc')

        self.assertEqual(r.method, 'GET')
        self.assertEqual(r.url, 'http://example.com/abc?a=1')
        self.assertEqual(r.params, {'a': 'b'})
        self.assertEqual(r.route_params, {'route': 'param'})

        with self.assertRaises(TypeError):
            r.params['a'] = 'z'

        self.assertEqual(r.get_body(), b'abc')

        with self.assertRaisesRegex(ValueError, 'does not contain valid JSON'):
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
        r = bind_http.HttpRequest(
            'POST',
            'http://example.com/abc?a=1',
            headers={},
            params={},
            route_params={},
            body_type='json',
            body='{"a":1}')

        self.assertEqual(r.method, 'POST')
        self.assertEqual(r.url, 'http://example.com/abc?a=1')
        self.assertEqual(r.params, {})
        self.assertEqual(r.route_params, {})

        self.assertEqual(r.get_body(), b'{"a":1}')
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


class Converter(bind_meta.InConverter, binding='foo'):
    pass


class TestTriggerMetadataDecoder(unittest.TestCase):

    def test_scalar_typed_data_decoder_ok(self):
        metadata = {
            'int_as_json': bind_meta.Datum(type='json', value='1'),
            'int_as_string': bind_meta.Datum(type='string', value='1'),
            'int_as_int': bind_meta.Datum(type='int', value=1),
            'string_as_json': bind_meta.Datum(type='json', value='"aaa"'),
            'string_as_string': bind_meta.Datum(type='string', value='aaa'),
            'dict_as_json': bind_meta.Datum(type='json', value='{"foo":"bar"}')
        }

        cases = [
            ('int_as_json', int, 1),
            ('int_as_string', int, 1),
            ('int_as_int', int, 1),
            ('string_as_json', str, 'aaa'),
            ('string_as_string', str, 'aaa'),
            ('dict_as_json', dict, {'foo': 'bar'}),
        ]

        for field, pytype, expected in cases:
            with self.subTest(field=field):
                value = Converter._decode_trigger_metadata_field(
                    metadata, field, python_type=pytype)

                self.assertIsInstance(value, pytype)
                self.assertEqual(value, expected)

    def test_scalar_typed_data_decoder_not_ok(self):
        metadata = {
            'unsupported_type':
                bind_meta.Datum(type='bytes', value=b'aaa'),
            'unexpected_json':
                bind_meta.Datum(type='json', value='[1, 2, 3]'),
            'unexpected_data':
                bind_meta.Datum(type='json', value='"foo"'),
        }

        cases = [
            (
                'unsupported_type', int, ValueError,
                "unsupported type of field 'unsupported_type' in "
                "trigger metadata: bytes"
            ),
            (
                'unexpected_json', int, ValueError,
                "cannot convert value of field 'unexpected_json' in "
                "trigger metadata into int"
            ),
            (
                'unexpected_data', int, ValueError,
                "cannot convert value of field "
                "'unexpected_data' in trigger metadata into int: "
                "invalid literal for int"
            ),
            (
                'unexpected_data', (int, float), ValueError,
                "unexpected value type in field "
                "'unexpected_data' in trigger metadata: str, "
                "expected one of: int, float"
            ),
        ]

        for field, pytype, exc, msg in cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(exc, msg):
                    Converter._decode_trigger_metadata_field(
                        metadata, field, python_type=pytype)
