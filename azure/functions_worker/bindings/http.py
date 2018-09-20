import json
import types
import typing

from azure.functions import _abc as azf_abc
from azure.functions import _http as azf_http

from . import meta
from .. import protos


class HttpRequest(azf_abc.HttpRequest):
    """An HTTP request object."""

    __body_bytes: typing.Optional[bytes]
    __body_str: typing.Optional[str]

    def __init__(self, method: str, url: str, *,
                 headers: typing.Mapping[str, str],
                 params: typing.Mapping[str, str],
                 route_params: typing.Mapping[str, str],
                 body_type: meta.TypedDataKind,
                 body: typing.Union[str, bytes]) -> None:
        self.__method = method
        self.__url = url
        self.__headers = azf_http.HttpRequestHeaders(headers)
        self.__params = types.MappingProxyType(params)
        self.__route_params = types.MappingProxyType(route_params)
        self.__body_type = body_type

        if isinstance(body, str):
            self.__body_bytes = None
            self.__body_str = body
        elif isinstance(body, bytes):
            self.__body_bytes = body
            self.__body_str = None
        else:
            raise TypeError(
                f'unexpected HTTP request body type: {type(body).__name__}')

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

    @property
    def route_params(self):
        return self.__route_params

    def get_body(self) -> bytes:
        if self.__body_bytes is None:
            assert self.__body_str is not None
            self.__body_bytes = self.__body_str.encode('utf-8')
        return self.__body_bytes

    def get_json(self) -> typing.Any:
        if self.__body_type is meta.TypedDataKind.json:
            assert self.__body_str is not None
            return json.loads(self.__body_str)
        raise ValueError('HTTP request does not have JSON data attached')


class HttpResponseConverter(meta.OutConverter, binding='http'):

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (azf_abc.HttpResponse, str))

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        if isinstance(obj, azf_abc.HttpResponse):
            status = obj.status_code
            headers = dict(obj.headers)
            if 'content-type' not in headers:
                if obj.mimetype.startswith('text/'):
                    ct = f'{obj.mimetype}; charset={obj.charset}'
                else:
                    ct = f'{obj.mimetype}'
                headers['content-type'] = ct

            body = obj.get_body()
            if body is not None:
                body = protos.TypedData(bytes=body)
            else:
                body = protos.TypedData(bytes=b'')

            return protos.TypedData(
                http=protos.RpcHttp(
                    status_code=str(status),
                    headers=headers,
                    enable_content_negotiation=False,
                    body=body))

        raise NotImplementedError


class HttpRequestConverter(meta.InConverter,
                           binding='httpTrigger', trigger=True):

    @classmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, azf_abc.HttpRequest)

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> typing.Any:
        if data.WhichOneof('data') != 'http':
            raise NotImplementedError

        body_rpc_val = data.http.body
        body_rpc_type = body_rpc_val.WhichOneof('data')

        if body_rpc_type == 'json':
            body_type = meta.TypedDataKind.json
            body = body_rpc_val.json
        elif body_rpc_type == 'string':
            body_type = meta.TypedDataKind.string
            body = body_rpc_val.string
        elif body_rpc_type == 'bytes':
            body_type = meta.TypedDataKind.bytes
            body = body_rpc_val.bytes
        elif body_rpc_type is None:
            # Means an empty HTTP request body -- we don't want
            # `HttpResponse.get_body()` to return None as it would
            # make it more complicated to work with than necessary.
            # Therefore we normalize the body to an empty bytes
            # object.
            body_type = meta.TypedDataKind.bytes
            body = b''
        else:
            raise TypeError(
                f'unsupported HTTP body type from the incoming gRPC data: '
                f'{body_rpc_type}')

        return HttpRequest(
            method=data.http.method,
            url=data.http.url,
            headers=data.http.headers,
            params=data.http.query,
            route_params=data.http.params,
            body_type=body_type,
            body=body)
