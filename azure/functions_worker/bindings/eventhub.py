import json
import typing

from azure.functions import _eventhub

from . import meta
from .. import protos


class EventHubConverter(meta.InConverter, meta.OutConverter,
                        binding='eventHub'):

    @classmethod
    def check_input_type_annotation(
            cls, pytype: type, datatype: protos.BindingInfo.DataType) -> bool:
        if datatype is protos.BindingInfo.undefined:
            return issubclass(pytype, _eventhub.EventHubEvent)
        else:
            return False

    @classmethod
    def check_output_type_annotation(cls, pytype) -> bool:
        return (
            issubclass(pytype, (str, bytes))
            or (issubclass(pytype, typing.List)
                and issubclass(pytype.__args__[0], str))
        )

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> _eventhub.EventHubEvent:
        data_type = data.WhichOneof('data')

        if data_type == 'string':
            body = data.string.encode('utf-8')

        elif data_type == 'bytes':
            body = data.bytes

        elif data_type == 'json':
            body = data.json.encode('utf-8')

        else:
            raise NotImplementedError(
                f'unsupported event data payload type: {data_type}')

        return _eventhub.EventHubEvent(body=body)

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if isinstance(obj, str):
            data = protos.TypedData(string=obj)

        elif isinstance(obj, bytes):
            data = protos.TypedData(bytes=obj)

        elif isinstance(obj, list):
            data = protos.TypedData(json=json.dumps(obj))

        return data


class EventHubTriggerConverter(EventHubConverter,
                               binding='eventHubTrigger', trigger=True):

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> _eventhub.EventHubEvent:
        data_type = data.WhichOneof('data')

        if data_type == 'string':
            body = data.string.encode('utf-8')

        elif data_type == 'bytes':
            body = data.bytes

        elif data_type == 'json':
            body = data.json.encode('utf-8')

        else:
            raise NotImplementedError(
                f'unsupported event data payload type: {data_type}')

        return _eventhub.EventHubEvent(
            body=body,
            enqueued_time=cls._parse_datetime_metadata(
                trigger_metadata, 'EnqueuedTime'),
            partition_key=cls._decode_trigger_metadata_field(
                trigger_metadata, 'PartitionKey', python_type=str),
            sequence_number=cls._decode_trigger_metadata_field(
                trigger_metadata, 'SequenceNumber', python_type=int),
            offset=cls._decode_trigger_metadata_field(
                trigger_metadata, 'Offset', python_type=str)
        )
