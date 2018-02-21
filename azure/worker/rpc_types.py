"""Implementation of 'azure.functions' ABCs.

Also includes internal facilities for marshaling
and unmarshaling protobuf objects.
"""


import typing

import azure.functions as azf

from . import protos


class Out(azf.Out):
    def __init__(self):
        self.__value = None

    def set(self, val):
        self.__value = val

    def get(self):
        return self.__value


class Context(azf.Context):

    def __init__(self, func_name, func_dir, invocation_id):
        self.__func_name = func_name
        self.__func_dir = func_dir
        self.__invocation_id = invocation_id

    @property
    def invocation_id(self) -> str:
        return self.__invocation_id

    @property
    def function_name(self) -> str:
        return self.__func_name

    @property
    def function_directory(self) -> str:
        return self.__func_dir


def from_incoming_proto(o: protos.TypedData):
    dt = o.WhichOneof('data')

    if dt is None:
        return

    if dt in {'string', 'json', 'bytes', 'stream', 'int', 'double'}:
        return getattr(o, dt)

    if dt == 'http':
        return azf.HttpRequest(
            method=o.http.method,
            url=o.http.url,
            headers=o.http.headers,
            params=o.http.query,
            body=from_incoming_proto(o.http.body))

    raise TypeError(
        f'unable to decode incoming TypedData: '
        f'unknown type of TypedData.data: {dt!r}')


def to_outgoing_proto(o: typing.Any):
    if o is None:
        return None

    if isinstance(o, int):
        return protos.TypedData(int=o)

    if isinstance(o, str):
        return protos.TypedData(string=o)

    if isinstance(o, bytes):
        return protos.TypedData(bytes=o)

    if isinstance(o, azf.HttpResponse):
        status = o.status_code
        headers = dict(o.headers)
        if 'content-type' not in headers:
            if o.mimetype.startswith('text/'):
                headers['content-type'] = f'{o.mimetype}; charset={o.charset}'
            else:
                headers['content-type'] = f'{o.mimetype}'

        body = o.get_body()
        if body is not None:
            body = protos.TypedData(bytes=body)
        else:
            body = protos.TypedData(bytes=b'')

        return protos.TypedData(
            http=protos.RpcHttp(
                status_code=str(status),
                headers=headers,
                is_raw=True,
                body=body))

    raise TypeError(
        f'unable to encode outgoing TypedData: '
        f'unsupported Python type: {type(o)}')
