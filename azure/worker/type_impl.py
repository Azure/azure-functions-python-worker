"""Implementation of 'azure.functions' ABCs."""

import enum
import json
import types
import typing

from azure.functions import _abc as azf_abc
from azure.functions import _http as azf_http


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
    timerTrigger = 'timerTrigger'


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
                 body_type: BindType,
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
        if self.__body_type is BindType.json:
            return json.loads(self.__body)
        raise ValueError('HTTP request does not have JSON data attached')
