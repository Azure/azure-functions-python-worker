# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# mypy: disable-error-code="attr-defined"
import os
import sys

from typing import Any, Dict, Optional, Union

from .datumdef import Datum, datum_as_proto
from .generic import GenericBinding

from ..http_v2 import HttpV2Registry
from ..logging import logger
from ..utils.constants import (
    BASE_EXT_SUPPORTED_PY_MINOR_VERSION,
    CUSTOMER_PACKAGES_PATH,
    HTTP,
    HTTP_TRIGGER,
)


PB_TYPE = 'rpc_data'
PB_TYPE_DATA = 'data'
PB_TYPE_RPC_SHARED_MEMORY = 'rpc_shared_memory'

BINDING_REGISTRY = None
DEFERRED_BINDING_REGISTRY = None


def _check_http_input_type_annotation(bind_name: str, pytype: type,
                                      is_deferred_binding: bool) -> bool:
    if HttpV2Registry.http_v2_enabled():
        return HttpV2Registry.ext_base().RequestTrackerMeta \
            .check_type(pytype)

    binding = get_binding(bind_name, is_deferred_binding)
    return binding.check_input_type_annotation(pytype)


def _check_http_output_type_annotation(bind_name: str, pytype: type) -> bool:
    if HttpV2Registry.http_v2_enabled():
        return HttpV2Registry.ext_base().ResponseTrackerMeta.check_type(pytype)

    binding = get_binding(bind_name)
    return binding.check_output_type_annotation(pytype)


INPUT_TYPE_CHECK_OVERRIDE_MAP = {
    HTTP_TRIGGER: _check_http_input_type_annotation
}

OUTPUT_TYPE_CHECK_OVERRIDE_MAP = {
    HTTP: _check_http_output_type_annotation
}


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
    BINDING_REGISTRY = func.get_binding_registry()  # type: ignore

    if BINDING_REGISTRY is None:
        raise AttributeError('BINDING_REGISTRY is None. azure-functions '
                             'library not found. Sys Path: %s. '
                             'Sys Modules: %s. '
                             'python-packages Path exists: %s.',
                             sys.path, sys.modules,
                             os.path.exists(CUSTOMER_PACKAGES_PATH))

    if sys.version_info.minor >= BASE_EXT_SUPPORTED_PY_MINOR_VERSION:
        try:
            import azurefunctions.extensions.base as clients
            global DEFERRED_BINDING_REGISTRY
            DEFERRED_BINDING_REGISTRY = clients.get_binding_registry()
        except ImportError:
            logger.debug('Base extension not found. '
                         'Python version: 3.%s, Sys path: %s, '
                         'Sys Module: %s, python-packages Path exists: %s.',
                         sys.version_info.minor, sys.path,
                         sys.modules, os.path.exists(CUSTOMER_PACKAGES_PATH))


def get_binding(bind_name: str,
                is_deferred_binding: Optional[bool] = False)\
        -> object:
    """
    First checks if the binding is a non-deferred binding. This is
    the most common case.
    Second checks if the binding is a deferred binding.
    If the binding is neither, it's a generic type.
    """
    binding = None
    if binding is None and not is_deferred_binding:
        binding = BINDING_REGISTRY.get(bind_name)  # type: ignore
    if binding is None and is_deferred_binding:
        binding = DEFERRED_BINDING_REGISTRY.get(bind_name)  # type: ignore
    if binding is None:
        binding = GenericBinding
    return binding


def is_trigger_binding(bind_name: str) -> bool:
    binding = get_binding(bind_name)
    return binding.has_trigger_support()


def check_input_type_annotation(bind_name: str,
                                pytype: type,
                                is_deferred_binding: bool) -> bool:
    global INPUT_TYPE_CHECK_OVERRIDE_MAP
    if bind_name in INPUT_TYPE_CHECK_OVERRIDE_MAP:
        return INPUT_TYPE_CHECK_OVERRIDE_MAP[bind_name](bind_name, pytype,
                                                        is_deferred_binding)

    binding = get_binding(bind_name, is_deferred_binding)

    return binding.check_input_type_annotation(pytype)


def check_output_type_annotation(bind_name: str, pytype: type) -> bool:
    global OUTPUT_TYPE_CHECK_OVERRIDE_MAP
    if bind_name in OUTPUT_TYPE_CHECK_OVERRIDE_MAP:
        return OUTPUT_TYPE_CHECK_OVERRIDE_MAP[bind_name](bind_name, pytype)

    binding = get_binding(bind_name)
    return binding.check_output_type_annotation(pytype)


def has_implicit_output(bind_name: str) -> bool:
    binding = get_binding(bind_name)

    # Need to pass in bind_name to exempt Durable Functions
    if binding is GenericBinding:
        return (getattr(binding, 'has_implicit_output', lambda: False)
                (bind_name))  # type: ignore

    else:
        # If the binding does not have metaclass of meta.InConverter
        # The implicit_output does not exist
        return getattr(binding, 'has_implicit_output', lambda: False)()


def from_incoming_proto(
        binding: str,
        pb, *,
        pytype: Optional[type],
        trigger_metadata: Optional[Dict[str, Any]],
        function_name: str,
        is_deferred_binding: Optional[bool] = False) -> Any:
    binding_obj = get_binding(binding, is_deferred_binding)
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
        # if the binding is an sdk type binding
        if is_deferred_binding:
            return deferred_bindings_decode(binding=binding_obj,
                                            pb=pb,
                                            pytype=pytype,
                                            datum=datum,
                                            metadata=metadata,
                                            function_name=function_name)
        return binding_obj.decode(datum, trigger_metadata=metadata)
    except NotImplementedError:
        # Binding does not support the data.
        dt = val.WhichOneof('data')
        raise TypeError(
            'unable to decode incoming TypedData: '
            'unsupported combination of TypedData field %s '
            'and expected binding type %s', repr(dt), binding_obj)


def get_datum(binding: str, obj: Any,
              pytype: Optional[type]) -> Union[Datum, None]:
    """
    Convert an object to a datum with the specified type.
    """
    binding_obj = get_binding(binding)
    try:
        datum = binding_obj.encode(obj, expected_type=pytype)
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
    return datum_as_proto(datum, protos)  # type: ignore


def to_outgoing_param_binding(binding: str, obj: Any, *,
                              pytype: Optional[type],
                              out_name: str,
                              protos):
    datum = get_datum(binding, obj, pytype)
    # If not, send it as part of the response message over RPC
    # rpc_val can be None here as we now support a None return type
    rpc_val = datum_as_proto(datum, protos)  # type: ignore
    return protos.ParameterBinding(
        name=out_name,
        data=rpc_val)


def deferred_bindings_decode(binding: Any,
                             pb: Any, *,
                             pytype: Optional[type],
                             datum: Any,
                             metadata: Any,
                             function_name: str):
    """
    The extension manages a cache for clients (ie. BlobClient, ContainerClient)
    That have already been created, so that the worker can reuse the
    Previously created type without creating a new one.

    For async types, the function_name is needed as a key to differentiate.
    This prevents a known SDK issue where reusing a client across functions
    can lose the session context and cause an error.

    The cache key is based on: param name, type, resource, function_name

    If cache is empty or key doesn't exist, deferred_binding_type is None
    """

    deferred_binding_type = binding.decode(datum,
                                           trigger_metadata=metadata,
                                           pytype=pytype)

    return deferred_binding_type


def check_deferred_bindings_enabled(param_anno: Union[type, None],
                                    deferred_bindings_enabled: bool) -> Any:
    """
    Checks if deferred bindings is enabled at fx and single binding level

    The first bool represents if deferred bindings is enabled at a fx level
    The second represents if the current binding is deferred binding
    """
    if (DEFERRED_BINDING_REGISTRY is not None
            and DEFERRED_BINDING_REGISTRY.check_supported_type(param_anno)):
        return True, True
    else:
        return deferred_bindings_enabled, False


def get_deferred_raw_bindings(indexed_function, input_types):
    """
    Calls a method from the base extension that generates the raw bindings
    for a given function. It also returns logs for that function including
    the defined binding type and if deferred bindings is enabled for that
    binding.
    """
    raw_bindings, bindings_logs = DEFERRED_BINDING_REGISTRY.get_raw_bindings(
        indexed_function, input_types)
    return raw_bindings, bindings_logs
