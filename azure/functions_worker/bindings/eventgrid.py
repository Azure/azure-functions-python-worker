import json
import typing

from azure.functions import _eventgrid

from . import meta
from .. import protos


class EventGridEventInConverter(meta.InConverter,
                                binding='eventGridTrigger', trigger=True):

    @classmethod
    def check_input_type_annotation(
            cls, pytype: type, datatype: protos.BindingInfo.DataType) -> bool:
        if datatype is protos.BindingInfo.undefined:
            return issubclass(pytype, _eventgrid.EventGridEvent)
        else:
            return False

    @classmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> typing.Any:
        data_type = data.WhichOneof('data')

        if data_type == 'json':
            body = json.loads(data.json)
        else:
            raise NotImplementedError(
                f'unsupported event grid payload type: {data_type}')

        if trigger_metadata is None:
            raise NotImplementedError(
                f'missing trigger metadata for event grid input')

        return _eventgrid.EventGridEvent(
            id=body.get('id'),
            topic=body.get('topic'),
            subject=body.get('subject'),
            event_type=body.get('eventType'),
            event_time=cls._parse_datetime(body.get('eventTime')),
            data=body.get('data'),
            data_version=body.get('dataVersion'),
        )
