# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys

from typing import Any, Dict, Optional

from .datumdef import Datum, datum_as_proto
from .generic import GenericBinding

from ..utils.constants import (
    CUSTOMER_PACKAGES_PATH,
)

PB_TYPE = 'rpc_data'
PB_TYPE_DATA = 'data'
PB_TYPE_RPC_SHARED_MEMORY = 'rpc_shared_memory'


def _check_http_input_type_annotation(bind_name: str, pytype: type) -> bool:
    binding = get_binding(bind_name)
    return binding.check_input_type_annotation(pytype)


def _check_http_output_type_annotation(bind_name: str, pytype: type) -> bool:
    binding = get_binding(bind_name)
    return binding.check_output_type_annotation(pytype)


def load_binding_registry() -> None:
    """
    Tries to load azure-functions from the customer's BYO. If it's
    not found, it loads the builtin. If the BINDING_REGISTRY is None,
    azure-functions hasn't been loaded in properly.

    Tries to load the base extension only for python 3.8+.
    """
    func = sys.modules.get('azure.functions')
    if func is None:
        import azure.functions as func

    global BINDING_REGISTRY
    BINDING_REGISTRY = func.get_binding_registry()

    if BINDING_REGISTRY is None:
        raise AttributeError('BINDING_REGISTRY is None. azure-functions '
                             'library not found. Sys Path: %s. '
                             'Sys Modules: %s. '
                             'python-packages Path exists: %s.',
                             sys.path, sys.modules,
                             os.path.exists(CUSTOMER_PACKAGES_PATH))


def get_binding(bind_name: str)\
        -> object:
    """
    First checks if the binding is not generic.
    If binding is still None, it's a generic type.
    """
    binding = BINDING_REGISTRY.get(bind_name)
    if binding is None:
        binding = GenericBinding
    return binding


def is_trigger_binding(bind_name: str) -> bool:
    binding = get_binding(bind_name)
    return binding.has_trigger_support()


def check_input_type_annotation(bind_name: str,
                                pytype: type) -> bool:
    binding = get_binding(bind_name)

    return binding.check_input_type_annotation(pytype)


def check_output_type_annotation(bind_name: str, pytype: type) -> bool:
    binding = get_binding(bind_name)
    return binding.check_output_type_annotation(pytype)


def has_implicit_output(bind_name: str) -> bool:
    binding = get_binding(bind_name)

    # Need to pass in bind_name to exempt Durable Functions
    if binding is GenericBinding:
        return (getattr(binding, 'has_implicit_output', lambda: False)
                (bind_name))

    else:
        # If the binding does not have metaclass of meta.InConverter
        # The implicit_output does not exist
        return getattr(binding, 'has_implicit_output', lambda: False)()


def from_incoming_proto(
        binding: str,
        pb, *,
        trigger_metadata: Optional[Dict[str, Any]]) -> Any:
    binding_obj = get_binding(binding)
    if trigger_metadata:
        metadata = {
            k: Datum.from_typed_data(v)
            for k, v in trigger_metadata.items()
        }
    else:
        metadata = {}

    pb_type = pb.WhichOneof(PB_TYPE)
    if pb_type == PB_TYPE_DATA:
        val = pb.data
        datum = Datum.from_typed_data(val)
    else:
        raise TypeError('Unknown ParameterBindingType: %s', pb_type)

    try:
        return binding_obj.decode(datum, trigger_metadata=metadata)
    except NotImplementedError:
        # Binding does not support the data.
        dt = val.WhichOneof('data')
        raise TypeError(
            'unable to decode incoming TypedData: '
            'unsupported combination of TypedData field %s '
            'and expected binding type %s', repr(dt), binding_obj)


def get_datum(binding: str, obj: Any,
              pytype: Optional[type]) -> Datum:
    """
    Convert an object to a datum with the specified type.
    """
    binding = get_binding(binding)
    try:
        datum = binding.encode(obj, expected_type=pytype)
    except NotImplementedError:
        # Binding does not support the data.
        raise TypeError(
            'unable to encode outgoing TypedData: '
            'unsupported type "%s" for '
            'Python type "%s"', binding, type(obj).__name__)
    return datum


def _does_datatype_support_caching(datum: Datum):
    supported_datatypes = ('bytes', 'string')
    return datum.type in supported_datatypes


def to_outgoing_proto(binding: str, obj: Any, *,
                      pytype: Optional[type],
                      protos):
    datum = get_datum(binding, obj, pytype)
    return datum_as_proto(datum, protos)


def to_outgoing_param_binding(binding: str, obj: Any, *,
                              pytype: Optional[type],
                              out_name: str,
                              protos):
    datum = get_datum(binding, obj, pytype)
    # If not, send it as part of the response message over RPC
    # rpc_val can be None here as we now support a None return type
    rpc_val = datum_as_proto(datum, protos)
    return protos.ParameterBinding(
        name=out_name,
        data=rpc_val)
