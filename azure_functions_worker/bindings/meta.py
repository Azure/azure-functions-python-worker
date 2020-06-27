# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import typing

from .. import protos

from . import datumdef
from . import generic


def get_binding_registry():
    func = sys.modules.get('azure.functions')

    # If fails to acquire customer's BYO azure-functions, load the builtin
    if func is None:
        import azure.functions as func

    return func.get_binding_registry()


def get_binding(bind_name: str) -> object:
    binding = None
    registry = get_binding_registry()
    if registry is not None:
        binding = registry.get(bind_name)
    if binding is None:
        binding = generic.GenericBinding

    return binding


def is_trigger_binding(bind_name: str) -> bool:
    binding = get_binding(bind_name)
    return binding.has_trigger_support()


def check_input_type_annotation(bind_name: str, pytype: type) -> bool:
    binding = get_binding(bind_name)
    return binding.check_input_type_annotation(pytype)


def check_output_type_annotation(bind_name: str, pytype: type) -> bool:
    binding = get_binding(bind_name)
    return binding.check_output_type_annotation(pytype)


def has_implicit_output(bind_name: str) -> bool:
    binding = get_binding(bind_name)

    # If the binding does not have metaclass of meta.InConverter
    # The implicit_output does not exist
    return getattr(binding, 'has_implicit_output', lambda: False)()


def from_incoming_proto(
        binding: str,
        val: protos.TypedData, *,
        pytype: typing.Optional[type],
        trigger_metadata: typing.Optional[typing.Dict[str, protos.TypedData]])\
        -> typing.Any:

    binding = get_binding(binding)
    datum = datumdef.Datum.from_typed_data(val)
    if trigger_metadata:
        metadata = {
            k: datumdef.Datum.from_typed_data(v)
            for k, v in trigger_metadata.items()
        }
    else:
        metadata = {}

    try:
        return binding.decode(datum, trigger_metadata=metadata)
    except NotImplementedError:
        # Binding does not support the data.
        dt = val.WhichOneof('data')

        raise TypeError(
            f'unable to decode incoming TypedData: '
            f'unsupported combination of TypedData field {dt!r} '
            f'and expected binding type {binding}')


def to_outgoing_proto(binding: str, obj: typing.Any, *,
                      pytype: typing.Optional[type]) -> protos.TypedData:
    binding = get_binding(binding)

    try:
        datum = binding.encode(obj, expected_type=pytype)
    except NotImplementedError:
        # Binding does not support the data.
        raise TypeError(
            f'unable to encode outgoing TypedData: '
            f'unsupported type "{binding}" for '
            f'Python type "{type(obj).__name__}"')

    return datumdef.datum_as_proto(datum)
