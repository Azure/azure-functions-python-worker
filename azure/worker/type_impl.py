"""Implementation of 'azure.functions' ABCs."""

import enum
import json
import io
import types
import typing

from azure.functions import _abc as azf_abc
from azure.functions import _http as azf_http


class TypedDataKind(enum.Enum):

    json = 1
    string = 2
    bytes = 3
    int = 4
    double = 5
    http = 6
    stream = 7


class Out(azf_abc.Out):

    def __init__(self):
        self.__value = None

    def set(self, val):
        self.__value = val

    def get(self):
        return self.__value


class Context(azf_abc.Context):

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


class HttpRequest(azf_abc.HttpRequest):
    """An HTTP request object."""

    def __init__(self, method: str, url: str,
                 headers: typing.Mapping[str, str],
                 params: typing.Mapping[str, str],
                 body_type: TypedDataKind,
                 body: typing.Union[str, bytes]) -> None:
        self.__method = method
        self.__url = url
        self.__headers = azf_http.HttpRequestHeaders(headers)
        self.__params = types.MappingProxyType(params)
        self.__body_type = body_type
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

    def get_body(self) -> typing.Union[str, bytes]:
        return self.__body

    def get_json(self) -> typing.Any:
        if self.__body_type is TypedDataKind.json:
            return json.loads(self.__body)
        raise ValueError('HTTP request does not have JSON data attached')


class TimerRequest(azf_abc.TimerRequest):

    def __init__(self, *, past_due: bool) -> None:
        self.__past_due = past_due

    @property
    def past_due(self):
        return self.__past_due


class InputStream(azf_abc.InputStream):
    def __init__(self, *, data: bytes) -> None:
        self._io = io.BytesIO(data)

    def read(self, size=-1) -> bytes:
        return self._io.read(size)

    def read1(self, size=-1) -> bytes:
        return self._io.read(size)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def writable(self) -> bool:
        return False
