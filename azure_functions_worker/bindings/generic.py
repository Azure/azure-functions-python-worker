# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing

from . import datumdef
from typing import Any, Optional


class GenericBindingProperties:

    def __init__(self, *,
                 bind_name: Optional[str] = None,):
        self.__bind_name = bind_name

    @property
    def get_bind_name(self) -> Optional[str]:
        return self.__bind_name

    @property
    def special_case_bind_names(self) -> list:
        return ["durableClient", "table"]


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
    def encode(cls, obj: Any, *,
               expected_type: Optional[type]) -> datumdef.Datum:
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

    @classmethod
    def has_implicit_output(cls,
                            properties:
                            Optional[GenericBindingProperties] = None) -> bool:
        if (properties and properties.get_bind_name in
                properties.special_case_bind_names):
            return False
        else:
            return True
