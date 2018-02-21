import collections.abc
import types
import typing

from . import _abc


class BaseHeaders(collections.abc.Mapping):

    def __init__(self, source=None):
        if source is None:
            self.__http_headers__ = {}
        else:
            self.__http_headers__ = {k.lower(): v for k, v in source.items()}

    def __getitem__(self, key: str) -> str:
        return self.__http_headers__[key.lower()]

    def __len__(self):
        return len(self.__http_headers__)

    def __contains__(self, key: str):
        return key.lower() in self.__http_headers__

    def __iter__(self):
        return iter(self.__http_headers__)


class RequestHeaders(BaseHeaders):
    pass


class ResponseHeaders(BaseHeaders, collections.abc.MutableMapping):

    def __setitem__(self, key: str, value: str):
        self.__http_headers__[key.lower()] = value

    def __delitem__(self, key: str):
        del self.__http_headers__[key.lower()]


class HttpRequest(_abc.HttpRequest):
    """An HTTP request object."""

    def __init__(self, method: str, url: str,
                 headers: typing.Mapping[str, str],
                 params: typing.Mapping[str, str],
                 body):
        self.__method = method
        self.__url = url
        self.__headers = BaseHeaders(headers)
        self.__params = types.MappingProxyType(params)
        self.__body = body

    @property
    def url(self):
        return self.__url

    @property
    def method(self):
        return self.__method.upper()

    @property
    def headers(self):
        return self.__headers

    @property
    def params(self):
        return self.__params

    def get_body(self):
        return self.__body


class HttpResponse(_abc.HttpResponse):
    """An HTTP response object."""

    def __init__(self, body=None, *,
                 status_code=None, headers=None, mimetype=None, charset=None):
        if status_code is None:
            status_code = 200
        self.__status_code = status_code

        if mimetype is None:
            mimetype = 'text/plain'
        self.__mimetype = mimetype

        if charset is None:
            charset = 'utf-8'
        self.__charset = charset

        if headers is None:
            headers = {}
        self.__headers = ResponseHeaders(headers)

        if body is not None:
            self.__set_body(body)
        else:
            self.__body = None

    @property
    def mimetype(self):
        return self.__mimetype

    @property
    def charset(self):
        return self.__charset

    @property
    def headers(self):
        return self.__headers

    @property
    def status_code(self):
        return self.__status_code

    def __set_body(self, body):
        if isinstance(body, str):
            body = body.encode(self.__charset)

        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(
                f'reponse is expected to be either of '
                f'str, bytes, or bytearray, got {type(body).__name__}')

        self.__body = body

    def get_body(self):
        return self.__body
