import sys
import unittest
from http.cookies import SimpleCookie
from unittest import skipIf

from dateutil import parser
from dateutil.parser import ParserError

from azure_functions_worker import protos
from azure_functions_worker.bindings.datumdef import \
    parse_cookie_attr_expires, \
    parse_cookie_attr_same_site, parse_to_rpc_http_cookie_list
from azure_functions_worker.bindings.nullable_converters import \
    to_nullable_bool, to_nullable_string, to_nullable_double, \
    to_nullable_timestamp
from azure_functions_worker.protos import RpcHttpCookie


class TestDatumRef(unittest.TestCase):
    def test_parse_cookie_attr_expires_none(self):
        self.assertEqual(parse_cookie_attr_expires({"expires": None}), None)

    def test_parse_cookie_attr_expires_zero_length(self):
        self.assertEqual(parse_cookie_attr_expires({"expires": ""}), None)

    def test_parse_cookie_attr_expires_valid(self):
        self.assertEqual(parse_cookie_attr_expires(
            {"expires": "Thu, 12-Jan-2017 13:55:08 GMT"}),
            parser.parse("Thu, 12-Jan-2017 13:55:08 GMT"))

    def test_parse_cookie_attr_expires_parse_error(self):
        with self.assertRaises(ParserError):
            parse_cookie_attr_expires(
                {"expires": "Thu, 12-Jan-2017 13:550:08 GMT"})

    def test_parse_cookie_attr_expires_overflow_error(self):
        with self.assertRaises(OverflowError):
            parse_cookie_attr_expires(
                {"expires": "Thu, 12-Jan-9999999999999999 13:550:08 GMT"})

    def test_parse_cookie_attr_same_site_default(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {}),
            getattr(protos.RpcHttpCookie.SameSite, "None"))

    def test_parse_cookie_attr_same_site_lax(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {'samesite': 'lax'}),
            getattr(protos.RpcHttpCookie.SameSite, "Lax"))

    def test_parse_cookie_attr_same_site_strict(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {'samesite': 'strict'}),
            getattr(protos.RpcHttpCookie.SameSite, "Strict"))

    def test_parse_cookie_attr_same_site_explicit_none(self):
        self.assertEqual(parse_cookie_attr_same_site(
            {'samesite': 'none'}),
            getattr(protos.RpcHttpCookie.SameSite, "ExplicitNone"))

    def test_parse_to_rpc_http_cookie_list_none(self):
        self.assertEqual(parse_to_rpc_http_cookie_list(None), None)

    @skipIf(sys.version_info < (3, 8, 0),
            "Skip the tests for Python 3.7 and below")
    def test_parse_to_rpc_http_cookie_list_valid(self):
        headers = [
            'foo=bar; Path=/some/path; Secure; HttpOnly; Domain=123; '
            'SameSite=Lax; Max-Age=12345; Expires=Thu, 12-Jan-2017 13:55:08 '
            'GMT;',
            'foo2=bar; Path=/some/path2; Secure; HttpOnly; Domain=123; '
            'SameSite=Lax; Max-Age=12345; Expires=Thu, 12-Jan-2017 13:55:08 '
            'GMT;']

        cookies = SimpleCookie('\r\n'.join(headers))

        cookie1 = RpcHttpCookie(name="foo",
                                value="bar",
                                domain=to_nullable_string("123",
                                                          "cookie.domain"),
                                path=to_nullable_string("/some/path",
                                                        "cookie.path"),
                                expires=to_nullable_timestamp(
                                    parse_cookie_attr_expires(
                                        {
                                            "expires": "Thu, "
                                                       "12-Jan-2017 13:55:08"
                                                       " GMT"}),
                                    'cookie.expires'),
                                secure=to_nullable_bool(
                                    bool("True"),
                                    'cookie.secure'),
                                http_only=to_nullable_bool(
                                    bool("True"),
                                    'cookie.httpOnly'),
                                same_site=parse_cookie_attr_same_site(
                                    {"samesite": "Lax"}),
                                max_age=to_nullable_double(
                                    12345,
                                    'cookie.maxAge'))

        cookie2 = RpcHttpCookie(name="foo2",
                                value="bar",
                                domain=to_nullable_string("123",
                                                          "cookie.domain"),
                                path=to_nullable_string("/some/path2",
                                                        "cookie.path"),
                                expires=to_nullable_timestamp(
                                    parse_cookie_attr_expires(
                                        {
                                            "expires": "Thu, "
                                                       "12-Jan-2017 13:55:08"
                                                       " GMT"}),
                                    'cookie.expires'),
                                secure=to_nullable_bool(
                                    bool("True"),
                                    'cookie.secure'),
                                http_only=to_nullable_bool(
                                    bool("True"),
                                    'cookie.httpOnly'),
                                same_site=parse_cookie_attr_same_site(
                                    {"samesite": "Lax"}),
                                max_age=to_nullable_double(
                                    12345,
                                    'cookie.maxAge'))

        rpc_cookies = parse_to_rpc_http_cookie_list([cookies])
        self.assertEqual(cookie1, rpc_cookies[0])
        self.assertEqual(cookie2, rpc_cookies[1])
