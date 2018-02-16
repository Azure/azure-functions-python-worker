"""Helpers to invoke Python functions."""


import inspect
import typing

from . import protos
from . import types


def parse_input_data(data: typing.Iterable[protos.ParameterBinding]):
    params = {}
    for pb in data:
        params[pb.name] = types.from_incoming_proto(pb.data)
    return params


def call(func: typing.Callable,
         ctx: types.Context,
         input_data: typing.Iterable[protos.ParameterBinding]):

    # TODO: Handle OutputBindings

    params = parse_input_data(input_data)

    sig = inspect.signature(func)

    # Cache the signature object so that the next `inspect.signature`
    # call is faster.
    func.__signature__ = sig

    if 'context' in sig.parameters:
        params['context'] = ctx

    return func(**params)
