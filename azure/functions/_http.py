import collections.abc
import typing

from . import _abc


class BaseHeaders(collections.abc.Mapping):

    def __init__(self, source: typing.Optional[typing.Mapping]=None) -> None:
        self.__http_headers__: typing.Dict[str, str] = {}

        if source is not None:
            self.__http_headers__.update(
                {k.lower(): v for k, v in source.items()})

    def __getitem__(self, key: str) -> str:
        return self.__http_headers__[key.lower()]

    def __len__(self):
        return len(self.__http_headers__)

    def __contains__(self, key: typing.Any):
        return key.lower() in self.__http_headers__

    def __iter__(self):
        return iter(self.__http_headers__)


class HttpRequestHeaders(BaseHeaders):
    pass


class HttpResponseHeaders(BaseHeaders, collections.abc.MutableMapping):

    def __setitem__(self, key: str, value: str):
        self.__http_headers__[key.lower()] = value

    def __delitem__(self, key: str):
        del self.__http_headers__[key.lower()]


class HttpResponse(_abc.HttpResponse):
    """An HTTP response object.

    :param str/bytes body:
        Optional response body.

    :param int status_code:
        Response status code.  If not specified, defaults to 200.

    :param dict headers:
        An optional mapping containing response HTTP headers.

    :param str mimetype:
        An optional response MIME type.  If not specified, defaults to
        ``'text/plain'``.

    :param str charset:
        Response content text encoding.  If not specified, defaults to
        ``'utf-8'``.
    """

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
        self.__headers = HttpResponseHeaders(headers)

        if body is not None:
            self.__set_body(body)
        else:
            self.__body = b''

    @property
    def mimetype(self):
        """Response MIME type."""
        return self.__mimetype

    @property
    def charset(self):
        """Response text encoding."""
        return self.__charset

    @property
    def headers(self):
        """A dictionary of response HTTP headers."""
        return self.__headers

    @property
    def status_code(self):
        """Response status code."""
        return self.__status_code

    def __set_body(self, body):
        if isinstance(body, str):
            body = body.encode(self.__charset)

        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(
                f'reponse is expected to be either of '
                f'str, bytes, or bytearray, got {type(body).__name__}')

        self.__body = bytes(body)

    def get_body(self) -> bytes:
        """Response body as a bytes object."""
        return self.__body
