import datetime
import json
import typing

import azure.functions as azf

from . import protos
from . import type_impl
from . import type_meta


class HttpResponseConverter(type_meta.OutConverter,
                            binding=type_meta.Binding.http):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, (azf.HttpResponse, str))

    @classmethod
    def to_proto(cls, obj: typing.Any) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        if isinstance(obj, azf.HttpResponse):
            status = obj.status_code
            headers = dict(obj.headers)
            if 'content-type' not in headers:
                if obj.mimetype.startswith('text/'):
                    ct = f'{obj.mimetype}; charset={obj.charset}'
                else:
                    ct = f'{obj.mimetype}'
                headers['content-type'] = ct

            body = obj.get_body()
            if body is not None:
                body = protos.TypedData(bytes=body)
            else:
                body = protos.TypedData(bytes=b'')

            return protos.TypedData(
                http=protos.RpcHttp(
                    status_code=str(status),
                    headers=headers,
                    is_raw=True,
                    body=body))

        raise NotImplementedError


class HttpRequestConverter(type_meta.InConverter,
                           binding=type_meta.Binding.httpTrigger):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, azf.HttpRequest)

    @classmethod
    def from_proto(cls, data: protos.TypedData,
                   trigger_metadata) -> typing.Any:
        if data.WhichOneof('data') != 'http':
            raise NotImplementedError

        body_rpc_val = data.http.body
        body_rpc_type = body_rpc_val.WhichOneof('data')

        if body_rpc_type == 'json':
            body_type = type_impl.TypedDataKind.json
            body = body_rpc_val.json
        elif body_rpc_type == 'string':
            body_type = type_impl.TypedDataKind.string
            body = body_rpc_val.string
        elif body_rpc_type == 'bytes':
            body_type = type_impl.TypedDataKind.bytes
            body = body_rpc_val.bytes
        elif body_rpc_type is None:
            # Means an empty HTTP request body -- we don't want
            # `HttpResponse.get_body()` to return None as it would
            # make it more complicated to work with than necessary.
            # Therefore we normalize the body to an empty bytes
            # object.
            body_type = type_impl.TypedDataKind.bytes
            body = ''
        else:
            raise TypeError(
                f'unsupported HTTP body type from the incoming gRPC data: '
                f'{body_rpc_type}')

        return type_impl.HttpRequest(
            method=data.http.method,
            url=data.http.url,
            headers=data.http.headers,
            params=data.http.query,
            body_type=body_type,
            body=body)


class TimerRequestConverter(type_meta.InConverter,
                            binding=type_meta.Binding.timerTrigger):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, azf.TimerRequest)

    @classmethod
    def from_proto(cls, data: protos.TypedData,
                   trigger_metadata) -> typing.Any:
        if data.WhichOneof('data') != 'json':
            raise NotImplementedError

        info = json.loads(data.json)
        return type_impl.TimerRequest(
            past_due=info.get('IsPastDue', False))


class BlobConverter(type_meta.InConverter,
                    type_meta.OutConverter,
                    binding=type_meta.Binding.blob):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return (issubclass(pytype, (str, bytes, bytearray,
                                    azf.InputStream) or
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

        return type_impl.InputStream(data=data)


class BlobTriggerConverter(BlobConverter,
                           binding=type_meta.Binding.blobTrigger):
    pass


class QueueMessageInConverter(type_meta.InConverter,
                              binding=type_meta.Binding.queueTrigger):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, azf.QueueMessage)

    @classmethod
    def from_proto(cls, data: protos.TypedData,
                   trigger_metadata) -> azf.QueueMessage:
        data_type = data.WhichOneof('data')

        if data_type == 'string':
            body = data.string

        elif data_type == 'bytes':
            body = data.bytes

        else:
            raise NotImplementedError(
                f'unsupported queue payload type: {data_type}')

        if trigger_metadata is None:
            raise NotImplementedError(
                f'missing trigger metadata for queue input')

        return type_impl.QueueMessage(
            id=cls._decode_scalar_typed_data(
                trigger_metadata.get('Id')),
            body=body,
            dequeue_count=cls._decode_scalar_typed_data(
                trigger_metadata.get('DequeueCount')),
            expiration_time=cls._parse_datetime(
                trigger_metadata.get('ExpirationTime')),
            insertion_time=cls._parse_datetime(
                trigger_metadata.get('InsertionTime')),
            next_visible_time=cls._parse_datetime(
                trigger_metadata.get('NextVisibleTime')),
            pop_receipt=cls._decode_scalar_typed_data(
                trigger_metadata.get('PopReceipt'))
        )

    @classmethod
    def _parse_datetime(cls, data: typing.Optional[protos.TypedData]):
        if data is None:
            return None
        else:
            datetime_str = cls._decode_scalar_typed_data(data)
            if not isinstance(datetime_str, str):
                data_type = data.WhichOneof('data')
                raise NotImplementedError(
                    f'unsupported type of a datetime field '
                    f'in trigger metadata: {data_type}')

        # UTC ISO 8601 assumed
        dt = datetime.datetime.strptime(
            datetime_str, '%Y-%m-%dT%H:%M:%S+00:00')
        return dt.replace(tzinfo=datetime.timezone.utc)


class QueueMessageOutConverter(type_meta.OutConverter,
                               binding=type_meta.Binding.queue):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, (azf.QueueMessage, str, bytes))

    @classmethod
    def to_proto(cls, obj: typing.Any) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        if isinstance(obj, azf.QueueMessage):
            return protos.TypedData(
                json=json.dumps({
                    'id': obj.id,
                    'body': obj.get_body().decode('utf-8'),
                })
            )

        raise NotImplementedError

    @classmethod
    def _format_datetime(cls, dt: typing.Optional[datetime.datetime]):
        if dt is None:
            return None
        else:
            return dt.isoformat()
