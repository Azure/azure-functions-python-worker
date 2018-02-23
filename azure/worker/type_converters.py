"""Facilities for marshaling and unmarshaling gRPC objects."""

import json
import typing

import azure.functions as azf

from . import protos
from . import type_impl

from .type_impl import BindType


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
        # We support returning 'str' values from http returning functions
        # as a shortcut for returning `HttpResponse(status_code=200, data)`.
        return issubclass(py_type, (azf.HttpResponse, str))

    if bind_type is BindType.httpTrigger:
        return issubclass(py_type, azf.HttpRequest)

    if bind_type is BindType.timerTrigger:
        return issubclass(py_type, azf.TimerRequest)

    raise TypeError(
        f'bind type {bind_type} does not have a corresponding Python type')


def from_incoming_proto(o_type: BindType, o: protos.TypedData) -> typing.Any:
    dt = o.WhichOneof('data')

    if o_type is BindType.string and dt == 'string':
        return o.string

    if o_type is BindType.bytes and dt == 'bytes':
        return o.bytes

    if o_type is BindType.httpTrigger and dt == 'http':
        body_rpc_val = o.http.body
        body_rpc_type = body_rpc_val.WhichOneof('data')

        body: typing.Any = None
        if body_rpc_type == 'json':
            body_type = BindType.json
        elif body_rpc_type == 'string':
            body_type = BindType.string
        elif body_rpc_type == 'bytes':
            body_type = BindType.bytes
        elif body_rpc_type is None:
            # Means an empty HTTP request body -- we don't want
            # `HttpResponse.get_body()` to return None as it would
            # make it more complicated to work with than necessary.
            # Therefore we normalize the body to an empty bytes
            # object.
            body_type = BindType.bytes
            body = ''
        else:
            raise TypeError(
                f'unsupported HTTP body type from the incoming gRPC data: '
                f'{body_rpc_type}')

        if body is None:
            # Not yet decoded from `body_rpc_val`.
            body = from_incoming_proto(body_type, body_rpc_val)

        return type_impl.HttpRequest(
            method=o.http.method,
            url=o.http.url,
            headers=o.http.headers,
            params=o.http.query,
            body_type=body_type,
            body=body)

    if o_type is BindType.json and dt == 'json':
        return o.json

    if o_type is BindType.int and dt == 'int':
        return o.int

    if o_type is BindType.double and dt == 'double':
        return o.double

    if o_type is BindType.timerTrigger and dt == 'json':
        info = json.loads(o.json)
        return type_impl.TimerRequest(
            past_due=info.get('IsPastDue', False))

    raise TypeError(
        f'unable to decode incoming TypedData: '
        f'unsupported combination of TypedData field {dt!r} '
        f'and expected Python type {o_type}')


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
