# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import typing

from .. import protos

from . import datumdef
from . import generic
from .shared_memory_data_transfer import SharedMemoryManager

PB_TYPE = 'rpc_data'
PB_TYPE_DATA = 'data'
PB_TYPE_RPC_SHARED_MEMORY = 'rpc_shared_memory'


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
        pb: protos.ParameterBinding, *,
        pytype: typing.Optional[type],
        trigger_metadata: typing.Optional[typing.Dict[str, protos.TypedData]],
        shmem_mgr: SharedMemoryManager) -> typing.Any:
    binding = get_binding(binding)
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
        rpc_val = datumdef.datum_as_proto(datum)
        if rpc_val is None:
            raise TypeError('Cannot convert datum to rpc_val')
        return protos.ParameterBinding(
            name=out_name,
            data=rpc_val)
