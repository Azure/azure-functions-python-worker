import datetime
import json
import typing

from azure.functions import _abc as funcabc

from . import meta
from .. import protos


class EventHubEvent(funcabc.EventHubEvent):
    """A concrete implementation of Event Hub message type."""

    def __init__(self, *,
                 body: bytes,
                 enqueued_time: typing.Optional[datetime.datetime]=None,
                 partition_key: typing.Optional[str]=None,
                 sequence_number: typing.Optional[int]=None,
                 offset: typing.Optional[str]=None) -> None:
        self.__body = body
        self.__enqueued_time = enqueued_time
        self.__partition_key = partition_key
        self.__sequence_number = sequence_number
        self.__offset = offset

    def get_body(self) -> bytes:
        return self.__body

    @property
    def partition_key(self) -> typing.Optional[str]:
        return self.__partition_key

    @property
    def sequence_number(self) -> typing.Optional[int]:
        return self.__sequence_number

    @property
    def enqueued_time(self) -> typing.Optional[datetime.datetime]:
        return self.__enqueued_time

    @property
    def offset(self) -> typing.Optional[str]:
        return self.__offset

    def __repr__(self) -> str:
        return (
            f'<azure.EventHubEvent '
            f'partition_key={self.partition_key} '
            f'sequence_number={self.sequence_number} '
            f'enqueued_time={self.enqueued_time} '
            f'at 0x{id(self):0x}>'
        )


class EventHubConverter(meta.InConverter, meta.OutConverter,
                        binding='eventHub'):

    @classmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, funcabc.EventHubEvent)

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
                   trigger_metadata) -> funcabc.EventHubEvent:
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

        return EventHubEvent(body=body)

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
                   trigger_metadata) -> funcabc.EventHubEvent:
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

        return EventHubEvent(
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
