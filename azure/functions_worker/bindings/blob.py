import io
import typing

from azure.functions import _abc as azf_abc

from . import meta
from .. import protos


class InputStream(azf_abc.InputStream):
    def __init__(self, *, data: bytes,
                 name: typing.Optional[str]=None,
                 uri: typing.Optional[str]=None,
                 length: typing.Optional[int]=None) -> None:
        self._io = io.BytesIO(data)
        self._name = name
        self._length = length
        self._uri = uri

    @property
    def name(self) -> typing.Optional[str]:
        return self._name

    @property
    def length(self) -> typing.Optional[int]:
        return self._length

    @property
    def uri(self) -> typing.Optional[str]:
        return self._uri

    def read(self, size=-1) -> bytes:
        return self._io.read(size)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False

    def writable(self) -> bool:
        return False


class BlobConverter(meta.InConverter,
                    meta.OutConverter,
                    binding='blob'):

    @classmethod
    def check_input_type_annotation(
            cls, pytype: type, datatype: protos.BindingInfo.DataType) -> bool:
        if (datatype is protos.BindingInfo.undefined
                or datatype is protos.BindingInfo.stream):
            return issubclass(pytype, azf_abc.InputStream)
        elif (datatype is protos.BindingInfo.binary):
            return issubclass(pytype, bytes)
        elif (datatype is protos.BindingInfo.string):
            return issubclass(pytype, str)
        else:  # Unknown datatype
            return False

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return (issubclass(pytype, (str, bytes, bytearray,
                                    azf_abc.InputStream) or
                callable(getattr(pytype, 'read', None))))

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if callable(getattr(obj, 'read', None)):
            # file-like object
            obj = obj.read()

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
                    f'unexpected type of data received for the "blob" binding '
                    f'declared to receive a string: {data_type!r}'
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
                    f'unexpected type of data received for the "blob" binding '
                    f'declared to receive bytes: {data_type!r}'
                )

        if data_type == 'string':
            data = data.string.encode('utf-8')
        elif data_type == 'bytes':
            data = data.bytes
        else:
            raise ValueError(
                f'unexpected type of data received for the "blob" binding '
                f': {data_type!r}'
            )

        if trigger_metadata is None:
            return InputStream(data=data)
        else:
            properties = cls._decode_trigger_metadata_field(
                trigger_metadata, 'Properties', python_type=dict)
            if properties:
                length = properties.get('Length')
                if length:
                    length = int(length)
                else:
                    length = None
            else:
                length = None

            return InputStream(
                data=data,
                name=cls._decode_trigger_metadata_field(
                    trigger_metadata, 'BlobTrigger', python_type=str),
                length=length,
                uri=cls._decode_trigger_metadata_field(
                    trigger_metadata, 'Uri', python_type=str),
            )


class BlobTriggerConverter(BlobConverter,
                           binding='blobTrigger', trigger=True):
    pass
