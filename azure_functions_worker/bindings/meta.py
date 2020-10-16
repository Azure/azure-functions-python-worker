# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys
import typing

from .. import protos

from . import datumdef
from . import generic
from .shared_memory_manager import SharedMemoryManager


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
            k: datumdef.Datum.from_typed_data(v, shmem_mgr)
            for k, v in trigger_metadata.items()
        }
    else:
        metadata = {}

    pb_type = pb.WhichOneof('rpc_data')
    if pb_type == 'rpc_shared_memory':
        # Data was sent over shared memory, attempt to read
        datum = datumdef.Datum.from_rpc_shared_memory(pb.rpc_shared_memory, shmem_mgr)
        # TODO gochaudh: check trigger_metadata (try with blob triggered func)
    elif pb_type == 'data':
        val = pb.data
        datum = datumdef.Datum.from_typed_data(val)
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


<<<<<<< HEAD
def get_datum(binding: str, obj: typing.Any,
              pytype: typing.Optional[type]) -> datumdef.Datum:
    """
    Convert an object to a datum with the specified type.
    """
=======
def to_outgoing_proto(binding: str, obj: typing.Any, *,
                      pytype: typing.Optional[type],
                      shmem_mgr: SharedMemoryManager,
                      invocation_id: str) -> protos.TypedData:
>>>>>>> Free shared memory resources after use
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

<<<<<<< HEAD

def to_outgoing_proto(binding: str, obj: typing.Any, *,
                      pytype: typing.Optional[type]) -> protos.TypedData:
    datum = get_datum(binding, obj, pytype)
    return datumdef.datum_as_proto(datum)


def to_outgoing_param_binding(binding: str, obj: typing.Any, *,
                      pytype: typing.Optional[type],
                      out_name: str,
                      shmem_mgr: SharedMemoryManager) -> protos.ParameterBinding:
    datum = get_datum(binding, obj, pytype)
    # TODO gochaudh: IMPORTANT: Right now we set the AppSetting to disable this
    # However that takes impact only for data coming from host -> worker
    # Is there a way to check the AppSetting here so that this does not respond back
    # with shared memory?
    shared_mem_value = None
    parameter_binding = None
    # If shared memory is enabled, try to transfer to host over shared memory
    if shmem_mgr.is_enabled() and shmem_mgr.is_supported(datum):
        shared_mem_value = datumdef.Datum.to_rpc_shared_memory(datum, shmem_mgr)
    if shared_mem_value is not None:
        # Check if data was transferred over shared memory.
        # If it was, then use the rpc_shared_memory field in the response message. 
        parameter_binding = protos.ParameterBinding(
                            name=out_name,
                            rpc_shared_memory=shared_mem_value)
    else:
        # If data was not trasnferred over shared memory, send it as part of the response message
        rpc_val = datumdef.datum_as_proto(datum)
        parameter_binding = protos.ParameterBinding(
                            name=out_name,
                            data=rpc_val)
    return parameter_binding
=======
    return datumdef.datum_as_proto(datum, shmem_mgr, invocation_id)
>>>>>>> Free shared memory resources after use
