import io
import typing

from azure.functions import _abc as azf_abc

from . import meta
from .. import protos


class InputStream(azf_abc.InputStream):
    def __init__(self, *, data: bytes) -> None:
        self._io = io.BytesIO(data)

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
    def check_python_type(cls, pytype: type) -> bool:
        return (issubclass(pytype, (str, bytes, bytearray,
                                    azf_abc.InputStream) or
                callable(getattr(pytype, 'read', None))))

    @classmethod
    def to_proto(cls, obj: typing.Any) -> protos.TypedData:
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
    def from_proto(cls, data: protos.TypedData,
                   trigger_metadata) -> typing.Any:
        data_type = data.WhichOneof('data')
        if data_type == 'string':
            data = data.string.encode('utf-8')
        elif data_type == 'bytes':
            data = data.bytes
        else:
            raise NotImplementedError

        return InputStream(data=data)


class BlobTriggerConverter(BlobConverter,
                           binding='blobTrigger', trigger=True):
    pass
