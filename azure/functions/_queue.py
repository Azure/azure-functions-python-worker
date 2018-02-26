import datetime
import json
import typing

from . import _abc


class QueueMessage(_abc.QueueMessage):
    """An HTTP response object."""

    def __init__(self, *,
                 id: typing.Optional[str]=None,
                 body: typing.Optional[typing.Union[str, bytes]]=None,
                 pop_receipt: typing.Optional[str]=None) -> None:
        self.__id = id
        self.__body = b''
        self.__pop_receipt = pop_receipt

        if body is not None:
            self.__set_body(body)

    @property
    def id(self) -> typing.Optional[str]:
        return self.__id

    @property
    def dequeue_count(self) -> typing.Optional[int]:
        return None

    @property
    def expiration_time(self) -> typing.Optional[datetime.datetime]:
        return None

    @property
    def insertion_time(self) -> typing.Optional[datetime.datetime]:
        return None

    @property
    def next_visible_time(self) -> typing.Optional[datetime.datetime]:
        return None

    @property
    def pop_receipt(self) -> typing.Optional[str]:
        return self.__pop_receipt

    def __set_body(self, body):
        if isinstance(body, str):
            body = body.encode('utf-8')

        if not isinstance(body, (bytes, bytearray)):
            raise TypeError(
                f'reponse is expected to be either of '
                f'str, bytes, or bytearray, got {type(body).__name__}')

        self.__body = bytes(body)

    def get_body(self) -> bytes:
        return self.__body

    def get_json(self) -> typing.Any:
        return json.loads(self.__body)

    def __repr__(self) -> str:
        return (
            f'<azure.QueueMessage id={self.id} at 0x{id(self):0x}>'
        )
