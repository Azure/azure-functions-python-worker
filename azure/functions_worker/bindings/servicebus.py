import datetime
import typing

from azure.functions import _servicebus as azf_sbus

from . import meta
from .. import protos


class ServiceBusMessage(azf_sbus.ServiceBusMessage):
    """An HTTP response object."""

    def __init__(
            self, *,
            body: bytes,
            content_type: typing.Optional[str]=None,
            correlation_id: typing.Optional[str]=None,
            expiration_time: typing.Optional[datetime.datetime]=None,
            label: typing.Optional[str]=None,
            message_id: str,
            partition_key: typing.Optional[str]=None,
            reply_to: typing.Optional[str]=None,
            reply_to_session_id: typing.Optional[str]=None,
            scheduled_enqueue_time: typing.Optional[datetime.datetime]=None,
            session_id: typing.Optional[str]=None,
            time_to_live: typing.Optional[datetime.timedelta]=None,
            to: typing.Optional[str]=None,
            user_properties: typing.Dict[str, object]) -> None:

        self.__body = body
        self.__content_type = content_type
        self.__correlation_id = correlation_id
        self.__expiration_time = expiration_time
        self.__label = label
        self.__message_id = message_id
        self.__partition_key = partition_key
        self.__reply_to = reply_to
        self.__reply_to_session_id = reply_to_session_id
        self.__scheduled_enqueue_time = scheduled_enqueue_time
        self.__session_id = session_id
        self.__time_to_live = time_to_live
        self.__to = to
        self.__user_properties = user_properties

    def get_body(self) -> bytes:
        return self.__body

    @property
    def content_type(self) -> typing.Optional[str]:
        return self.__content_type

    @property
    def correlation_id(self) -> typing.Optional[str]:
        return self.__correlation_id

    @property
    def expiration_time(self) -> typing.Optional[datetime.datetime]:
        return self.__expiration_time

    @property
    def label(self) -> typing.Optional[str]:
        return self.__label

    @property
    def message_id(self) -> str:
        return self.__message_id

    @property
    def partition_key(self) -> typing.Optional[str]:
        return self.__partition_key

    @property
    def reply_to(self) -> typing.Optional[str]:
        return self.__reply_to

    @property
    def reply_to_session_id(self) -> typing.Optional[str]:
        return self.__reply_to_session_id

    @property
    def scheduled_enqueue_time(self) -> typing.Optional[datetime.datetime]:
        return self.__scheduled_enqueue_time

    @property
    def session_id(self) -> typing.Optional[str]:
        return self.__session_id

    @property
    def time_to_live(self) -> typing.Optional[datetime.timedelta]:
        return self.__time_to_live

    @property
    def to(self) -> typing.Optional[str]:
        return self.__to

    @property
    def user_properties(self) -> typing.Dict[str, object]:
        return self.__user_properties

    def __repr__(self) -> str:
        return (
            f'<azure.functions.ServiceBusMessage '
            f'message_id={self.message_id} '
            f'at 0x{id(self):0x}>'
        )


class ServiceBusMessageInConverter(meta.InConverter,
                                   binding='serviceBusTrigger', trigger=True):

    @classmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, azf_sbus.ServiceBusMessage)

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> typing.Any:
        data_type = data.WhichOneof('data')

        if data_type == 'string':
            body = data.string.encode('utf-8')

        elif data_type == 'bytes':
            body = data.bytes

        elif data_type == 'json':
            body = data.json.encode('utf-8')

        else:
            raise NotImplementedError(
                f'unsupported queue payload type: {data_type}')

        if trigger_metadata is None:
            raise NotImplementedError(
                f'missing trigger metadata for ServiceBus message input')

        return ServiceBusMessage(
            body=body,
            content_type=cls._decode_trigger_metadata_field(
                trigger_metadata, 'ContentType', python_type=str),
            correlation_id=cls._decode_trigger_metadata_field(
                trigger_metadata, 'CorrelationId', python_type=str),
            expiration_time=cls._parse_datetime_metadata(
                trigger_metadata, 'ExpirationTime'),
            label=cls._decode_trigger_metadata_field(
                trigger_metadata, 'Label', python_type=str),
            message_id=cls._decode_trigger_metadata_field(
                trigger_metadata, 'MessageId', python_type=str),
            partition_key=cls._decode_trigger_metadata_field(
                trigger_metadata, 'PartitionKey', python_type=str),
            reply_to=cls._decode_trigger_metadata_field(
                trigger_metadata, 'ReplyTo', python_type=str),
            reply_to_session_id=cls._decode_trigger_metadata_field(
                trigger_metadata, 'ReplyToSessionId', python_type=str),
            scheduled_enqueue_time=cls._parse_datetime_metadata(
                trigger_metadata, 'ScheduledEnqueueTime'),
            session_id=cls._decode_trigger_metadata_field(
                trigger_metadata, 'SessionId', python_type=str),
            time_to_live=cls._parse_timedelta_metadata(
                trigger_metadata, 'TimeToLive'),
            to=cls._decode_trigger_metadata_field(
                trigger_metadata, 'To', python_type=str),
            user_properties=cls._decode_trigger_metadata_field(
                trigger_metadata, 'UserProperties', python_type=dict),
        )


class ServiceBusMessageOutConverter(meta.OutConverter, binding='serviceBus'):

    @classmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        return issubclass(pytype, (str, bytes))

    @classmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        if isinstance(obj, str):
            return protos.TypedData(string=obj)

        elif isinstance(obj, bytes):
            return protos.TypedData(bytes=obj)

        raise NotImplementedError
