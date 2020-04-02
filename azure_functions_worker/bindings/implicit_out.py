import typing
import json

from . import datumdef


class ImplicitOutBinding:

    @classmethod
    def has_trigger_support(cls) -> bool:
        return False

    @classmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (int, float, bool, str, bytes, list, dict))

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (int, float, bool, str, bytes, list, dict))

    @classmethod
    def encode(cls, obj: typing.Any, *,
               expected_type: typing.Optional[type]) -> datumdef.Datum:
        if isinstance(obj, str):
            return datumdef.Datum(type='string', value=obj)

        elif isinstance(obj, (bytes, bytearray)):
            return datumdef.Datum(type='bytes', value=bytes(obj))

        else:
            return datumdef.Datum(type='json', value=json.dumps(obj))

    @classmethod
    def decode(cls, data: datumdef.Datum, *, trigger_metadata) -> typing.Any:
        data_type = data.type

        if data_type == 'string':
            result = data.value
        elif data_type == 'bytes':
            result = data.value
        elif data_type == 'json':
            result = json.loads(data.value)
        else:
            raise ValueError(
                f'unexpected type of data received for the "implicit_out" '
                f'binding: {data_type!r}'
            )

        return result

    @classmethod
    def has_implicit_output(cls) -> bool:
        return False
