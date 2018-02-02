"""Implementation of 'azure.functions' ABCs.

Also includes internal facilities for marshaling
and unmarshaling protobuf objects.
"""


import types
import typing

import azure.functions

from . import protos


class HttpRequest(azure.functions.HttpRequest):
    """An HTTP request object."""

    __slots__ = ('_method', '_url', '_headers', '_params', '_body')

    def __init__(self, method: str, url: str,
                 headers: typing.Mapping[str, str],
                 params: typing.Mapping[str, str],
                 body):
        self._method = method
        self._url = url
        self._headers = types.MappingProxyType(headers)
        self._params = types.MappingProxyType(params)
        self._body = body

    @property
    def url(self):
        return self._url

    @property
    def method(self):
        return self._method.upper()

    @property
    def headers(self):
        return self._headers

    @property
    def params(self):
        return self._params

    def get_body(self):
        return self._body


def from_incoming_proto(o: protos.TypedData):
    dt = o.WhichOneof('data')

    if dt is None:
        return

    if dt in {'string', 'json', 'bytes', 'stream', 'int', 'double'}:
        return getattr(o, dt)

    if dt == 'http':
        return HttpRequest(
            method=o.http.method,
            url=o.http.url,
            headers=o.http.headers,
            params=o.http.params,
            body=from_incoming_proto(o.http.body))

    raise TypeError(
        f'unable to decode incoming TypedData: '
        f'unknown type of TypedData.data: {dt!r}')


def to_outgoing_proto(o: typing.Any):
    if isinstance(o, int):
        return protos.TypedData(int=o)

    if isinstance(o, str):
        return protos.TypedData(string=o)

    if isinstance(o, bytes):
        return protos.TypedData(bytes=o)

    raise TypeError(
        f'unable to encode outgoing TypedData: '
        f'unsupported Python type: {type(o)}')
