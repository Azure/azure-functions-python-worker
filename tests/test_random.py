import unittest

from azure_functions_worker.bindings.datumdef import parse_cookie_attr_expires, \
    parse_to_rpc_http_cookie_list

try:
    from http.cookies import SimpleCookie
except ImportError:
    from Cookie import SimpleCookie
from dateutil import parser

headers = ['foo=bar; Path=/some/path; Secure',
           'foo2=42; Domain=123; Expires=Thu, 12-Jan-2017 13:55:08 GMT; '
           'Path=/; Max-Age=dd;']

cookies = SimpleCookie('\r\n'.join(headers))


class TestHttpFunctions(unittest.TestCase):
    def test_multiple_cookie_header_in_response(self):
        print(parse_to_rpc_http_cookie_list([cookies]))
