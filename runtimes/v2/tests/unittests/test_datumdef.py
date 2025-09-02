# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import unittest

import tests.protos as protos

from datetime import datetime
from http.cookies import SimpleCookie

from azure_functions_runtime.bindings.datumdef import (
    Datum,
    parse_cookie_attr_expires,
    parse_cookie_attr_same_site,
    parse_to_rpc_http_cookie_list,
)
from azure_functions_runtime.bindings.nullable_converters import (
    to_nullable_bool,
    to_nullable_double,
    to_nullable_string,
    to_nullable_timestamp,
)


class TestDatumDef(unittest.TestCase):
    def test_parse_cookie_attr_expires_none(self):
        self.assertEqual(parse_cookie_attr_expires({"expires": None}), None)

    def test_parse_cookie_attr_expires_zero_length(self):
        self.assertEqual(parse_cookie_attr_expires({"expires": ""}), None)

    def test_parse_cookie_attr_expires_valid(self):
        self.assertEqual(parse_cookie_attr_expires(
            {"expires": "Thu, 12 Jan 2017 13:55:08 GMT"}),
            datetime.strptime("Thu, 12 Jan 2017 13:55:08 GMT",
                              "%a, %d %b %Y %H:%M:%S GMT"))

    def test_parse_cookie_attr_expires_value_error(self):
        with self.assertRaises(ValueError):
            parse_cookie_attr_expires(
                {"expires": "Thu, 12 Jan 2017 13:550:08 GMT"})

    def test_parse_cookie_attr_expires_overflow_error(self):
        with self.assertRaises(ValueError):
            parse_cookie_attr_expires(
                {"expires": "Thu, 12 Jan 9999999999999999 13:55:08 GMT"})

    def test_parse_cookie_attr_same_site_default(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {}, protos),
            getattr(protos.RpcHttpCookie.SameSite, "None"))

    def test_parse_cookie_attr_same_site_lax(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {'samesite': 'lax'}, protos),
            getattr(protos.RpcHttpCookie.SameSite, "Lax"))

    def test_parse_cookie_attr_same_site_strict(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {'samesite': 'strict'}, protos),
            getattr(protos.RpcHttpCookie.SameSite, "Strict"))

    def test_parse_cookie_attr_same_site_explicit_none(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {'samesite': 'none'}, protos),
            getattr(protos.RpcHttpCookie.SameSite, "ExplicitNone"))

    def test_parse_to_rpc_http_cookie_list_none(self):
        self.assertEqual(parse_to_rpc_http_cookie_list(None, protos), None)

    def test_parse_to_rpc_http_cookie_list_valid(self):
        headers = [
            'foo=bar; Path=/some/path; Secure; HttpOnly; Domain=123; '
            'SameSite=Lax; Max-Age=12345; Expires=Thu, 12 Jan 2017 13:55:08 '
            'GMT;',
            'foo2=bar; Path=/some/path2; Secure; HttpOnly; Domain=123; '
            'SameSite=Lax; Max-Age=12345; Expires=Thu, 12 Jan 2017 13:55:08 '
            'GMT;']

        cookies = SimpleCookie('\r\n'.join(headers))

        cookie1 = protos.RpcHttpCookie(name="foo",
                                       value="bar",
                                       domain=to_nullable_string("123",
                                                                 "cookie.domain",
                                                                 protos),
                                       path=to_nullable_string("/some/path",
                                                               "cookie.path",
                                                               protos),
                                       expires=to_nullable_timestamp(
                                           parse_cookie_attr_expires(
                                               {
                                                   "expires": "Thu, "
                                                              "12 Jan 2017 13:55:08"
                                                              " GMT"}),
                                           'cookie.expires',
                                           protos),
                                       secure=to_nullable_bool(
                                           bool("True"),
                                           'cookie.secure',
                                           protos),
                                       http_only=to_nullable_bool(
                                           bool("True"),
                                           'cookie.httpOnly',
                                           protos),
                                       same_site=parse_cookie_attr_same_site(
                                           {"samesite": "Lax"},
                                           protos),
                                       max_age=to_nullable_double(
                                           12345,
                                           'cookie.maxAge',
                                           protos))

        cookie2 = protos.RpcHttpCookie(name="foo2",
                                       value="bar",
                                       domain=to_nullable_string("123",
                                                                 "cookie.domain",
                                                                 protos),
                                       path=to_nullable_string("/some/path2",
                                                               "cookie.path",
                                                               protos),
                                       expires=to_nullable_timestamp(
                                           parse_cookie_attr_expires(
                                               {
                                                   "expires": "Thu, "
                                                              "12 Jan 2017 13:55:08"
                                                              " GMT"}),
                                           'cookie.expires',
                                           protos),
                                       secure=to_nullable_bool(
                                           bool("True"),
                                           'cookie.secure',
                                           protos),
                                       http_only=to_nullable_bool(
                                           bool("True"),
                                           'cookie.httpOnly',
                                           protos),
                                       same_site=parse_cookie_attr_same_site(
                                           {"samesite": "Lax"},
                                           protos),
                                       max_age=to_nullable_double(
                                           12345,
                                           'cookie.maxAge',
                                           protos))

        rpc_cookies = parse_to_rpc_http_cookie_list([cookies], protos)
        self.assertEqual(cookie1, rpc_cookies[0])
        self.assertEqual(cookie2, rpc_cookies[1])

    def test_parse_to_rpc_http_cookie_list_no_cookie(self):
        datum = Datum(
            type='http',
            value=dict(
                status_code=None,
                headers=None,
                body=None,
            )
        )

        self.assertIsNone(
            parse_to_rpc_http_cookie_list(datum.value.get('cookies'), protos))
