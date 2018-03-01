import datetime
import json
import typing

from azure.functions import _abc as azf_abc
from azure.functions import _queue as azf_queue

from . import meta
from .. import protos


class QueueMessage(azf_queue.QueueMessage):
    """An HTTP response object."""

    def __init__(self, *,
                 id=None, body=None,
                 dequeue_count=None,
                 expiration_time=None,
                 insertion_time=None,
                 next_visible_time=None,
                 pop_receipt=None):
        super().__init__(id=id, body=body, pop_receipt=pop_receipt)
        self.__dequeue_count = dequeue_count
        self.__expiration_time = expiration_time
        self.__insertion_time = insertion_time
        self.__next_visible_time = next_visible_time

    @property
    def dequeue_count(self):
        return self.__dequeue_count

    @property
    def expiration_time(self):
        return self.__expiration_time

    @property
    def insertion_time(self):
        return self.__insertion_time

    @property
    def next_visible_time(self):
        return self.__next_visible_time

    def __repr__(self) -> str:
        return (
            f'<azure.QueueMessage id={self.id} '
            f'dequeue_count={self.dequeue_count} '
            f'insertion_time={self.insertion_time} '
            f'expiration_time={self.expiration_time} '
            f'at 0x{id(self):0x}>'
        )


class QueueMessageInConverter(meta.InConverter,
                              binding='queueTrigger', trigger=True):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, azf_abc.QueueMessage)

    @classmethod
    def from_proto(cls, data: protos.TypedData,
                   trigger_metadata) -> azf_abc.QueueMessage:
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

        return QueueMessage(
            id=cls._decode_trigger_metadata_field(
                trigger_metadata, 'Id', python_type=str),
            body=body,
            dequeue_count=cls._decode_trigger_metadata_field(
                trigger_metadata, 'DequeueCount', python_type=int),
            expiration_time=cls._parse_datetime_metadata(
                trigger_metadata, 'ExpirationTime'),
            insertion_time=cls._parse_datetime_metadata(
                trigger_metadata, 'InsertionTime'),
            next_visible_time=cls._parse_datetime_metadata(
                trigger_metadata, 'NextVisibleTime'),
            pop_receipt=cls._decode_trigger_metadata_field(
                trigger_metadata, 'PopReceipt', python_type=str)
        )

    @classmethod
    def _parse_datetime_metadata(
            cls, trigger_metadata: typing.Mapping[str, protos.TypedData],
            field: str) -> typing.Optional[datetime.datetime]:

        datetime_str = cls._decode_trigger_metadata_field(
            trigger_metadata, field, python_type=str)

        if datetime_str is None:
            return None
        else:
            # UTC ISO 8601 assumed
            dt = datetime.datetime.strptime(
                datetime_str, '%Y-%m-%dT%H:%M:%S+00:00')
            return dt.replace(tzinfo=datetime.timezone.utc)


class QueueMessageOutConverter(meta.OutConverter, binding='queue'):

    @classmethod
    def check_python_type(cls, pytype: type) -> bool:
        return issubclass(pytype, (azf_abc.QueueMessage, str, bytes))

    @classmethod
    def to_proto(cls, obj: typing.Any) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        if isinstance(obj, azf_queue.QueueMessage):
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
