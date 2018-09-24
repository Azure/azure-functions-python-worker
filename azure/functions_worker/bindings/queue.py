import collections.abc
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
                 time_next_visible=None,
                 pop_receipt=None):
        super().__init__(id=id, body=body, pop_receipt=pop_receipt)
        self.__dequeue_count = dequeue_count
        self.__expiration_time = expiration_time
        self.__insertion_time = insertion_time
        self.__time_next_visible = time_next_visible

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
    def time_next_visible(self):
        return self.__time_next_visible

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
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, azf_abc.QueueMessage)

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> typing.Any:
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
            time_next_visible=cls._parse_datetime_metadata(
                trigger_metadata, 'NextVisibleTime'),
            pop_receipt=cls._decode_trigger_metadata_field(
                trigger_metadata, 'PopReceipt', python_type=str)
        )


class QueueMessageOutConverter(meta.OutConverter, binding='queue'):

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        valid_types = (azf_abc.QueueMessage, str, bytes)
        return (
            meta.is_iterable_type_annotation(pytype, valid_types) or
            (isinstance(pytype, type) and issubclass(pytype, valid_types))
        )

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        elif isinstance(obj, bytes):
            return protos.TypedData(bytes=obj)

        elif isinstance(obj, azf_queue.QueueMessage):
            return protos.TypedData(
                json=json.dumps({
                    'id': obj.id,
                    'body': obj.get_body().decode('utf-8'),
                })
            )

        elif isinstance(obj, collections.abc.Iterable):
            msgs = []
            for item in obj:
                if isinstance(item, str):
                    msgs.append(item)
                elif isinstance(item, azf_queue.QueueMessage):
                    msgs.append({
                        'id': item.id,
                        'body': item.get_body().decode('utf-8')
                    })
                else:
                    raise NotImplementedError(
                        'invalid data type in output '
                        'queue message list: {}'.format(type(item)))

            return protos.TypedData(
                json=json.dumps(msgs)
            )

        raise NotImplementedError

    @classmethod
    def _format_datetime(cls, dt: typing.Optional[datetime.datetime]):
        if dt is None:
            return None
        else:
            return dt.isoformat()
