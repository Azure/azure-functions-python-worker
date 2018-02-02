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
         input_data: typing.Iterable[protos.ParameterBinding]):

    # TODO: Handle OutputBindings
    # TODO: Inject Context if needed

    params = parse_input_data(input_data)

    sig = inspect.signature(func)
    ba = sig.bind(**params)

    return func(*ba.args, **ba.kwargs)
