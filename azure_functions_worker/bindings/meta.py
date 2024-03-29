# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import typing

from .. import protos
from ..constants import BASE_EXT_SUPPORTED_PY_MINOR_VERSION

from . import datumdef
from . import generic
from .shared_memory_data_transfer import SharedMemoryManager

PB_TYPE = 'rpc_data'
PB_TYPE_DATA = 'data'
PB_TYPE_RPC_SHARED_MEMORY = 'rpc_shared_memory'
BINDING_REGISTRY = None
DEFERRED_BINDINGS_REGISTRY = None
DEFERRED_BINDINGS_ENABLED = False
DEFERRED_BINDINGS_CACHE = {}


def load_binding_registry() -> None:
    func = sys.modules.get('azure.functions')

    # If fails to acquire customer's BYO azure-functions, load the builtin
    if func is None:
        import azure.functions as func

    global BINDING_REGISTRY
    BINDING_REGISTRY = func.get_binding_registry()

    if BINDING_REGISTRY is None:
        # If the BINDING_REGISTRY is None, azure-functions hasn't been
        # loaded in properly.
        raise AttributeError("BINDING_REGISTRY is None.")

    # The base extension supports python 3.8+
    if sys.version_info.minor >= BASE_EXT_SUPPORTED_PY_MINOR_VERSION:
        # Import the base extension
        try:
            import azure.functions.extension.base as clients
            global DEFERRED_BINDINGS_REGISTRY
            DEFERRED_BINDINGS_REGISTRY = clients.get_binding_registry()
        except ImportError:
            # This means that the customer hasn't imported the library.
            # This isn't an error.
            pass


def get_binding(bind_name: str, pytype: typing.Optional[type] = None) -> object:
    # Check if binding is deferred binding
    binding = get_deferred_binding(bind_name=bind_name, pytype=pytype)
    # Binding is not a deferred binding type
    if binding is None:
        binding = BINDING_REGISTRY.get(bind_name)
    # Binding is generic
    if binding is None:
        binding = generic.GenericBinding
    return binding


def is_trigger_binding(bind_name: str) -> bool:
    binding = get_binding(bind_name)
    return binding.has_trigger_support()


def check_input_type_annotation(bind_name: str, pytype: type) -> bool:
    # check that needs to pass for sdk bindings -- pass in pytype
    binding = get_binding(bind_name, pytype)
    return binding.check_input_type_annotation(pytype)


def check_output_type_annotation(bind_name: str, pytype: type) -> bool:
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
        shmem_mgr: SharedMemoryManager) -> typing.Any:
    binding = get_binding(binding, pytype)
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
        if (DEFERRED_BINDINGS_REGISTRY is not None
                and DEFERRED_BINDINGS_REGISTRY.check_supported_type(pytype)):
            return deferred_bindings_decode(binding=binding,
                                            pb=pb,
                                            pytype=pytype,
                                            datum=datum,
                                            metadata=metadata)
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


def get_deferred_binding(bind_name: str,
                         pytype: typing.Optional[type] = None) -> object:
    binding = None

    # Checks if pytype is a supported sdk type
    if (DEFERRED_BINDINGS_REGISTRY is not None
            and DEFERRED_BINDINGS_REGISTRY.check_supported_type(pytype)):
        # Returns deferred binding converter
        binding = DEFERRED_BINDINGS_REGISTRY.get(bind_name)

    # This will return None if not a supported type
    return binding


def deferred_bindings_decode(binding: typing.Any,
                             pb: protos.ParameterBinding, *,
                             pytype: typing.Optional[type],
                             datum: typing.Any,
                             metadata: typing.Any):
    # This cache holds deferred binding types (ie. BlobClient, ContainerClient)
    # That have already been created, so that the worker can reuse the
    # Previously created type without creating a new one. It allows these
    # Types to be singleton.
    global DEFERRED_BINDINGS_CACHE

    # Check if the type is already in the cache
    # If dict is empty or key doesn't exist, deferred_binding_type is None
    deferred_binding_type = DEFERRED_BINDINGS_CACHE.get((pb.name, pytype,
                                                         datum.value.content),
                                                        None)

    # If the type is in the cache, return it
    if deferred_binding_type is not None:
        return deferred_binding_type
    # Otherwise, create the specified type and add it to the cache
    else:
        deferred_binding_type = binding.decode(datum, trigger_metadata=metadata,
                                               pytype=pytype)
        DEFERRED_BINDINGS_CACHE[(pb.name, pytype, datum.value.content)]\
            = deferred_binding_type
        return deferred_binding_type


def set_deferred_bindings_flag(param_anno: type):
    # If flag hasn't already been set
    # If DEFERRED_BINDINGS_REGISTRY is not None
    # If the binding type is a deferred binding type
    global DEFERRED_BINDINGS_ENABLED
    if (not DEFERRED_BINDINGS_ENABLED
            and DEFERRED_BINDINGS_REGISTRY is not None
            and DEFERRED_BINDINGS_REGISTRY.check_supported_type(param_anno)):
        DEFERRED_BINDINGS_ENABLED = True
