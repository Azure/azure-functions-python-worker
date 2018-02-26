import abc
import datetime
import io
import typing


T = typing.TypeVar('T')


class Out(abc.ABC, typing.Generic[T]):

    @abc.abstractmethod
    def set(self, val: T) -> None:
        pass

    @abc.abstractmethod
    def get(self) -> T:
        pass


class Context(abc.ABC):

    @property
    @abc.abstractmethod
    def invocation_id(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def function_name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def function_directory(self) -> str:
        pass


class HttpRequest(abc.ABC):

    @property
    @abc.abstractmethod
    def method(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def url(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def headers(self) -> typing.Mapping[str, str]:
        pass

    @property
    @abc.abstractmethod
    def params(self) -> typing.Mapping[str, str]:
        pass

    @abc.abstractmethod
    def get_body(self) -> typing.Union[str, bytes]:
        pass

    @abc.abstractmethod
    def get_json(self) -> typing.Any:
        pass


class HttpResponse(abc.ABC):

    @property
    @abc.abstractmethod
    def status_code(self) -> int:
        pass

    @property
    @abc.abstractmethod
    def headers(self) -> typing.MutableMapping[str, str]:
        pass

    @abc.abstractmethod
    def get_body(self) -> bytes:
        pass


class TimerRequest(abc.ABC):

    @property
    @abc.abstractmethod
    def past_due(self) -> bool:
        pass


class InputStream(io.BufferedIOBase, abc.ABC):

    @abc.abstractmethod
    def read(self, size=-1) -> bytes:
        pass


class QueueMessage(abc.ABC):

    @property
    @abc.abstractmethod
    def id(self) -> typing.Optional[str]:
        pass

    @abc.abstractmethod
    def get_body(self) -> typing.Union[str, bytes]:
        pass

    @abc.abstractmethod
    def get_json(self) -> typing.Any:
        pass

    @property
    @abc.abstractmethod
    def dequeue_count(self) -> typing.Optional[int]:
        pass

    @property
    @abc.abstractmethod
    def expiration_time(self) -> typing.Optional[datetime.datetime]:
        pass

    @property
    @abc.abstractmethod
    def insertion_time(self) -> typing.Optional[datetime.datetime]:
        pass

    @property
    @abc.abstractmethod
    def next_visible_time(self) -> typing.Optional[datetime.datetime]:
        pass

    @property
    @abc.abstractmethod
    def pop_receipt(self) -> typing.Optional[str]:
        pass
