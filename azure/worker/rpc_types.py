"""Implementation of 'azure.functions' ABCs.

Also includes internal facilities for marshaling
and unmarshaling protobuf objects.
"""


import enum
import typing

import azure.functions as azf

from . import protos


class BindType(str, enum.Enum):
    """Type names that can appear in FunctionLoadRequest/BindingInfo.

    See also the TypedData struct.
    """

    string = 'string'
    json = 'json'
    bytes = 'bytes'
    stream = 'stream'
    http = 'http'
    int = 'int'
    double = 'double'

    httpTrigger = 'httpTrigger'


class Out(azf.Out):

    def __init__(self):
        self.__value = None

    def set(self, val):
        self.__value = val

    def get(self):
        return self.__value


class Context(azf.Context):

    def __init__(self, func_name: str, func_dir: str,
                 invocation_id: str) -> None:
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


def check_bind_type_matches_py_type(
        bind_type: BindType, py_type: type) -> bool:

    if bind_type in {BindType.string, BindType.json}:
        return issubclass(py_type, str)

    if bind_type is BindType.bytes:
        return issubclass(py_type, (bytes, bytearray))

    if bind_type is BindType.int:
        return issubclass(py_type, int)

    if bind_type is BindType.double:
        return issubclass(py_type, float)

    if bind_type is BindType.http:
        return issubclass(py_type, azf.HttpResponse)

    if bind_type is BindType.httpTrigger:
        return issubclass(py_type, azf.HttpRequest)

    raise TypeError(
        f'bind type {bind_type} does not have a corresponding Python type')


def from_incoming_proto(o: protos.TypedData) -> typing.Any:
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


def to_outgoing_proto(o_type: BindType, o: typing.Any) -> protos.TypedData:
    assert o is not None

    if o_type is BindType.http:
        if isinstance(o, str):
            return to_outgoing_proto(BindType.string, o)

        if isinstance(o, azf.HttpResponse):
            status = o.status_code
            headers = dict(o.headers)
            if 'content-type' not in headers:
                if o.mimetype.startswith('text/'):
                    ct = f'{o.mimetype}; charset={o.charset}'
                else:
                    ct = f'{o.mimetype}'
                headers['content-type'] = ct

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

    elif o_type in {BindType.string, BindType.json}:
        if isinstance(o, str):
            return protos.TypedData(string=o)

    elif o_type is BindType.bytes:
        if isinstance(o, (bytes, bytearray)):
            return protos.TypedData(bytes=o)

    elif o_type is BindType.int:
        if isinstance(o, int):
            return protos.TypedData(int=o)

    elif o_type is BindType.double:
        if isinstance(o, float):
            return protos.TypedData(double=o)

    raise TypeError(
        f'unable to encode outgoing TypedData: '
        f'unsupported type "{o_type}" for Python type "{type(o).__name__}"')
