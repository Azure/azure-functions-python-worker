import abc
import typing


_T = typing.TypeVar('T')


class Out(abc.ABC, typing.Generic[_T]):

    @abc.abstractmethod
    def set(self, val: _T):
        pass

    @abc.abstractmethod
    def get(self) -> _T:
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

    def get_body(self) -> bytes:
        pass


class HttpResponse(abc.ABC):

    @property
    @abc.abstractmethod
    def status_code(self):
        pass

    @property
    @abc.abstractmethod
    def headers(self):
        pass

    @abc.abstractmethod
    def get_body(self) -> bytes:
        pass
