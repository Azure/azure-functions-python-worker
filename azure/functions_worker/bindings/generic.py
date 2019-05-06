import typing

from . import meta
from .. import protos


class GenericConverter(meta.InConverter,
                       meta.OutConverter,
                       binding='generic'):

    @classmethod
    def check_input_type_annotation(
            cls, pytype: type, datatype: protos.BindingInfo.DataType) -> bool:
        if (datatype is protos.BindingInfo.binary):
            return issubclass(pytype, bytes)
        elif (datatype is protos.BindingInfo.string):
            return issubclass(pytype, str)
        else:  # Unknown datatype
            return False

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (str, bytes, bytearray))

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        elif isinstance(obj, (bytes, bytearray)):
            return protos.TypedData(bytes=bytes(obj))

        else:
            raise NotImplementedError

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> typing.Any:
        data_type = data.WhichOneof('data')

        if pytype is str:
            # Bound as dataType: string
            if data_type == 'string':
                return data.string
            else:
                raise ValueError(
                    f'unexpected type of data received for the "generic" '
                    f'binding declared to receive a string: {data_type!r}'
                )

            return data.string

        elif pytype is bytes:
            if data_type == 'bytes':
                return data.bytes
            elif data_type == 'string':
                # This should not happen with the correct dataType spec,
                # but we can be forgiving in this case.
                return data.string.encode('utf-8')
            else:
                raise ValueError(
                    f'unexpected type of data received for the "generic" '
                    f'binding declared to receive bytes: {data_type!r}'
                )

        if data_type == 'string':
            data = data.string.encode('utf-8')
        elif data_type == 'bytes':
            data = data.bytes
        else:
            raise ValueError(
                f'unexpected type of data received for the "generic" binding '
                f': {data_type!r}'
            )

        return data
