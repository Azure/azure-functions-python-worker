# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys
import typing

from .. import protos
from ..constants import (
    BASE_EXT_SUPPORTED_PY_MINOR_VERSION,
    CUSTOMER_PACKAGES_PATH,
    HTTP,
    HTTP_TRIGGER,
    SERVICE_BUS_CLIENT_NAME
)
from ..http_v2 import HttpV2Registry
from ..logging import logger
from . import datumdef, generic
from .shared_memory_data_transfer import SharedMemoryManager

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
    BINDING_REGISTRY = func.get_binding_registry()

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
                is_deferred_binding: typing.Optional[bool] = False)\
        -> object:
    """
    First checks if the binding is a non-deferred binding. This is
    the most common case.
    Second checks if the binding is a deferred binding.
    If the binding is neither, it's a generic type.
    """
    binding = None
    if binding is None and not is_deferred_binding:
        binding = BINDING_REGISTRY.get(bind_name)
    if binding is None and is_deferred_binding:
        binding = DEFERRED_BINDING_REGISTRY.get(bind_name)
    if binding is None:
        binding = generic.GenericBinding
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
    if binding is generic.GenericBinding:
        return (getattr(binding, 'has_implicit_output', lambda: False)
                (bind_name))

    else:
        # If the binding does not have metaclass of meta.InConverter
        # The implicit_output does not exist
        return getattr(binding, 'has_implicit_output', lambda: False)()


def from_incoming_proto(
        binding: str,
        pb: protos.ParameterBinding, *,
        pytype: typing.Optional[type],
        trigger_metadata: typing.Optional[typing.Dict[str, protos.TypedData]],
        shmem_mgr: SharedMemoryManager,
        function_name: str,
        is_deferred_binding: typing.Optional[bool] = False) -> typing.Any:
    binding = get_binding(binding, is_deferred_binding)
    if trigger_metadata:
        metadata = {
            k: datumdef.Datum.from_typed_data(v)
            for k, v in trigger_metadata.items()
        }
    else:
        metadata = {}

    pb_type = pb.WhichOneof(PB_TYPE)
    if pb_type == PB_TYPE_DATA:
        val = pb.data
        datum = datumdef.Datum.from_typed_data(val)
    elif pb_type == PB_TYPE_RPC_SHARED_MEMORY:
        # Data was sent over shared memory, attempt to read
        datum = datumdef.Datum.from_rpc_shared_memory(pb.rpc_shared_memory,
                                                      shmem_mgr)
    else:
        raise TypeError(f'Unknown ParameterBindingType: {pb_type}')

    try:
        # if the binding is an sdk type binding
        if is_deferred_binding:
            return deferred_bindings_decode(binding=binding,
                                            pb=pb,
                                            pytype=pytype,
                                            datum=datum,
                                            metadata=metadata,
                                            function_name=function_name)
        return binding.decode(datum, trigger_metadata=metadata)
    except NotImplementedError:
        # Binding does not support the data.
        dt = val.WhichOneof('data')
        raise TypeError(
            f'unable to decode incoming TypedData: '
            f'unsupported combination of TypedData field {dt!r} '
            f'and expected binding type {binding}')


def get_datum(binding: str, obj: typing.Any,
              pytype: typing.Optional[type]) -> datumdef.Datum:
    """
    Convert an object to a datum with the specified type.
    """
    binding = get_binding(binding)
    try:
        datum = binding.encode(obj, expected_type=pytype)
    except NotImplementedError:
        # Binding does not support the data.
        raise TypeError(
            f'unable to encode outgoing TypedData: '
            f'unsupported type "{binding}" for '
            f'Python type "{type(obj).__name__}"')
    return datum


def _does_datatype_support_caching(datum: datumdef.Datum):
    supported_datatypes = ('bytes', 'string')
    return datum.type in supported_datatypes


def _can_transfer_over_shmem(shmem_mgr: SharedMemoryManager,
                             is_function_data_cache_enabled: bool,
                             datum: datumdef.Datum):
    """
    If shared memory is enabled and supported for the given datum, try to
    transfer to host over shared memory as a default.
    If caching is enabled, then also check if this type is supported - if so,
    transfer over shared memory.
    In case of caching, some conditions like object size may not be
    applicable since even small objects are also allowed to be cached.
    """
    if not shmem_mgr.is_enabled():
        # If shared memory usage is not enabled, no further checks required
        return False
    if shmem_mgr.is_supported(datum):
        # If transferring this object over shared memory is supported, do so.
        return True
    if is_function_data_cache_enabled and _does_datatype_support_caching(datum):
        # If caching is enabled and this object can be cached, transfer over
        # shared memory (since the cache uses shared memory).
        # In this case, some requirements (like object size) for using shared
        # memory may be ignored since we want to support caching of small
        # objects (those that have sizes smaller that the minimum we transfer
        # over shared memory when the cache is not enabled) as well.
        return True
    return False


def to_outgoing_proto(binding: str, obj: typing.Any, *,
                      pytype: typing.Optional[type]) -> protos.TypedData:
    datum = get_datum(binding, obj, pytype)
    return datumdef.datum_as_proto(datum)


def to_outgoing_param_binding(binding: str, obj: typing.Any, *,
                              pytype: typing.Optional[type],
                              out_name: str,
                              shmem_mgr: SharedMemoryManager,
                              is_function_data_cache_enabled: bool) \
        -> protos.ParameterBinding:
    datum = get_datum(binding, obj, pytype)
    shared_mem_value = None
    if _can_transfer_over_shmem(shmem_mgr, is_function_data_cache_enabled,
                                datum):
        shared_mem_value = datumdef.Datum.to_rpc_shared_memory(datum, shmem_mgr)
    # Check if data was written into shared memory
    if shared_mem_value is not None:
        # If it was, then use the rpc_shared_memory field in response message
        return protos.ParameterBinding(
            name=out_name,
            rpc_shared_memory=shared_mem_value)
    else:
        # If not, send it as part of the response message over RPC
        # rpc_val can be None here as we now support a None return type
        rpc_val = datumdef.datum_as_proto(datum)
        return protos.ParameterBinding(
            name=out_name,
            data=rpc_val)


def deferred_bindings_decode(binding: typing.Any,
                             pb: protos.ParameterBinding, *,
                             pytype: typing.Optional[type],
                             datum: typing.Any,
                             metadata: typing.Any,
                             function_name: str):

    return binding.decode(datum, trigger_metadata=metadata, pytype=pytype)


def check_deferred_bindings_enabled(
        param_anno: type,
        deferred_bindings_enabled: bool) -> typing.Tuple[bool, bool]:
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


def get_settlement_client():
    return DEFERRED_BINDING_REGISTRY.get(SERVICE_BUS_CLIENT_NAME).get_client()


def validate_settlement_param(params: dict,
                              bound_params: dict,
                              annotations: dict) -> str:
    """
    Checks if the settlement client is enabled for a given function.

    If there is more than one param that is not bound, return an empty string
    indicating no settlement client support. This is a bad app.

    If there is only one unbound param, check if it's a type that is supported
    by the settlement client. If so, return the param_name, where param_name
    is the name of the param that is supported. If not, return an empty string
    indicating no settlement client support.

    Note: If a param does not have a type annotation, it will be skipped and not
    considered for settlement client support.
    """
    if len(set(params) - set(bound_params)) > 1:
        return None

    # There is only one unbound param, check the type
    settlement_param = next(iter(set(params) - set(bound_params)))
    try:
        param_type = annotations.get(settlement_param)
        # Check if the type is a supported type for the settlement client
        if DEFERRED_BINDING_REGISTRY.check_supported_grpc_client_type(param_type):
            return settlement_param
    except Exception:
        param_type = None
    return None
