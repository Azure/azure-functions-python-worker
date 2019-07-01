import typing

from . import datumdef


class GenericBinding:

    @classmethod
    def has_trigger_support(cls) -> bool:
        return False

    @classmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (str, bytes))

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (str, bytes, bytearray))

    @classmethod
    def encode(cls, obj: typing.Any, *,
               expected_type: typing.Optional[type]) -> datumdef.Datum:
        if isinstance(obj, str):
            return datumdef.Datum(type='string', value=obj)

        elif isinstance(obj, (bytes, bytearray)):
            return datumdef.Datum(type='bytes', value=bytes(obj))

        else:
            raise NotImplementedError

    @classmethod
    def decode(cls, data: datumdef.Datum, *, trigger_metadata) -> typing.Any:
        data_type = data.type

        if data_type == 'string':
            result = data.value
        elif data_type == 'bytes':
            result = data.value
        elif data_type == 'json':
            result = data.value
        else:
            raise ValueError(
                f'unexpected type of data received for the "generic" binding '
                f': {data_type!r}'
            )

        return result
