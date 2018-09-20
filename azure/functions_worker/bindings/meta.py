import abc
import collections.abc
import datetime
import enum
import json
import typing

from .. import protos
from .. import typing_inspect


class TypedDataKind(enum.Enum):

    json = 1
    string = 2
    bytes = 3
    int = 4
    double = 5
    http = 6
    stream = 7


class _ConverterMeta(abc.ABCMeta):

    _check_in_typeann: typing.Mapping[str, typing.Callable[[type], bool]] = {}
    _check_out_typeann: typing.Mapping[str, typing.Callable[[type], bool]] = {}
    _from_proto: typing.Mapping[str, typing.Callable] = {}
    _to_proto: typing.Mapping[str, typing.Callable] = {}
    _binding_types: typing.Mapping[str, bool] = {}

    def __new__(mcls, name, bases, dct, *,
                binding: typing.Optional[str], trigger: bool=False):
        cls = super().__new__(mcls, name, bases, dct)
        if binding is None:
            return cls

        if binding in mcls._binding_types:
            raise RuntimeError(
                f'cannot register a converter for {binding!r} binding: '
                f'another converter for this binding has already been '
                f'registered')
        mcls._binding_types[binding] = trigger

        check_in_typesig = getattr(cls, 'check_input_type_annotation', None)
        if (check_in_typesig is not None and
                not getattr(check_in_typesig, '__isabstractmethod__', False)):
            if binding in mcls._check_in_typeann:
                raise RuntimeError(
                    f'cannot register a second check_input_type_annotation '
                    f'implementation for {binding!r} binding')
            mcls._check_in_typeann[binding] = check_in_typesig

        check_out_typesig = getattr(cls, 'check_output_type_annotation', None)
        if (check_out_typesig is not None and
                not getattr(check_out_typesig, '__isabstractmethod__', False)):
            if binding in mcls._check_out_typeann:
                raise RuntimeError(
                    f'cannot register a second check_output_type_annotation '
                    f'implementation for {binding!r} binding')
            mcls._check_out_typeann[binding] = check_out_typesig

        if issubclass(cls, InConverter):
            if binding in mcls._from_proto:
                raise RuntimeError(
                    f'cannot register a second from_proto implementation '
                    f'for {binding!r} binding')
            mcls._from_proto[binding] = getattr(cls, 'from_proto')

        if issubclass(cls, OutConverter):
            if binding in mcls._to_proto:
                raise RuntimeError(
                    f'cannot register a second to_proto implementation '
                    f'for {binding!r} binding')
            mcls._to_proto[binding] = getattr(cls, 'to_proto')

        return cls


class _BaseConverter(metaclass=_ConverterMeta, binding=None):

    @classmethod
    def _decode_typed_data(
            cls, data: typing.Optional[protos.TypedData], *,
            python_type: typing.Union[type, typing.Tuple[type, ...]],
            context: str='data') -> typing.Any:
        if data is None:
            return None

        data_type = data.WhichOneof('data')
        if data_type == 'json':
            result = json.loads(data.json)

        elif data_type == 'string':
            result = data.string

        elif data_type == 'int':
            result = data.int

        elif data_type == 'double':
            result = data.double

        else:
            raise ValueError(
                f'unsupported type of {context}: {data_type}')

        if not isinstance(result, python_type):
            if isinstance(python_type, (tuple, list, dict)):
                raise ValueError(
                    f'unexpected value type in {context}: '
                    f'{type(result).__name__}, expected one of: '
                    f'{", ".join(t.__name__ for t in python_type)}')
            else:
                try:
                    # Try coercing into the requested type
                    result = python_type(result)
                except (TypeError, ValueError) as e:
                    raise ValueError(
                        f'cannot convert value of {context} into '
                        f'{python_type.__name__}: {e}') from None

        return result

    @classmethod
    def _decode_trigger_metadata_field(
            cls, trigger_metadata: typing.Mapping[str, protos.TypedData],
            field: str, *,
            python_type: typing.Union[type, typing.Tuple[type, ...]]) \
            -> typing.Any:
        data = trigger_metadata.get(field)
        if data is None or data.WhichOneof('data') is None:
            return None
        else:
            return cls._decode_typed_data(
                data, python_type=python_type,
                context=f'field {field!r} in trigger metadata')

    @classmethod
    def _parse_datetime_metadata(
            cls, trigger_metadata: typing.Mapping[str, protos.TypedData],
            field: str) -> typing.Optional[datetime.datetime]:

        datetime_str = cls._decode_trigger_metadata_field(
            trigger_metadata, field, python_type=str)

        if datetime_str is None:
            return None
        else:
            return cls._parse_datetime(datetime_str)

    @classmethod
    def _parse_timedelta_metadata(
            cls, trigger_metadata: typing.Mapping[str, protos.TypedData],
            field: str) -> typing.Optional[datetime.timedelta]:

        timedelta_str = cls._decode_trigger_metadata_field(
            trigger_metadata, field, python_type=str)

        if timedelta_str is None:
            return None
        else:
            return cls._parse_timedelta(timedelta_str)

    @classmethod
    def _parse_datetime(
            cls, datetime_str: str) -> datetime.datetime:
        # UTC ISO 8601 assumed
        formats = [
            '%Y-%m-%dT%H:%M:%S+00:00',
            '%Y-%m-%dT%H:%M:%S.%f+00:00',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
        ]
        dt = None
        for fmt in formats:
            try:
                dt = datetime.datetime.strptime(datetime_str, fmt)
            except ValueError as e:
                last_error = e

        if dt is None:
            raise last_error

        return dt.replace(tzinfo=datetime.timezone.utc)

    @classmethod
    def _parse_timedelta(
            cls, timedelta_str: str) -> datetime.timedelta:
        raise NotImplementedError


class InConverter(_BaseConverter, binding=None):

    @abc.abstractclassmethod
    def check_input_type_annotation(cls, pytype: type) -> bool:
        pass

    @abc.abstractclassmethod
    def from_proto(cls, data: protos.TypedData, *,
                   pytype: typing.Optional[type],
                   trigger_metadata) -> typing.Any:
        pass


class OutConverter(_BaseConverter, binding=None):

    @abc.abstractclassmethod
    def check_output_type_annotation(cls, pytype: type) -> bool:
        pass

    @abc.abstractclassmethod
    def to_proto(cls, obj: typing.Any, *,
                 pytype: typing.Optional[type]) -> protos.TypedData:
        pass


def is_iterable_type_annotation(annotation: object, pytype: object) -> bool:
    is_iterable_anno = (
        typing_inspect.is_generic_type(annotation) and
        issubclass(typing_inspect.get_origin(annotation),
                   collections.abc.Iterable)
    )

    if not is_iterable_anno:
        return False

    args = typing_inspect.get_args(annotation)
    if not args:
        return False

    if isinstance(pytype, tuple):
        return any(isinstance(t, type) and issubclass(t, arg)
                   for t in pytype for arg in args)
    else:
        return any(isinstance(pytype, type) and issubclass(pytype, arg)
                   for arg in args)


def is_binding(bind_name: str) -> bool:
    return bind_name in _ConverterMeta._binding_types


def is_trigger_binding(bind_name: str) -> bool:
    try:
        return _ConverterMeta._binding_types[bind_name]
    except KeyError:
        raise ValueError(f'unsupported binding type {bind_name!r}')


def check_input_type_annotation(binding: str, pytype: type) -> bool:
    try:
        checker = _ConverterMeta._check_in_typeann[binding]
    except KeyError:
        raise TypeError(
            f'{binding!r} input binding does not have '
            f'a corresponding Python type') from None

    return checker(pytype)


def check_output_type_annotation(binding: str, pytype: type) -> bool:
    try:
        checker = _ConverterMeta._check_out_typeann[binding]
    except KeyError:
        raise TypeError(
            f'{binding!r} output binding does not have '
            f'a corresponding Python type') from None

    return checker(pytype)


def from_incoming_proto(
        binding: str, val: protos.TypedData, *,
        pytype: typing.Optional[type],
        trigger_metadata: typing.Optional[typing.Dict[str, protos.TypedData]])\
        -> typing.Any:
    converter = _ConverterMeta._from_proto.get(binding)

    try:
        try:
            converter = _ConverterMeta._from_proto[binding]
        except KeyError:
            raise NotImplementedError
        else:
            return converter(val, pytype=pytype,
                             trigger_metadata=trigger_metadata)
    except NotImplementedError:
        # Either there's no converter or a converter has failed.
        dt = val.WhichOneof('data')

        raise TypeError(
            f'unable to decode incoming TypedData: '
            f'unsupported combination of TypedData field {dt!r} '
            f'and expected binding type {binding}')


def to_outgoing_proto(binding: str, obj: typing.Any, *,
                      pytype: typing.Optional[type]) -> protos.TypedData:
    converter = _ConverterMeta._to_proto.get(binding)

    try:
        try:
            converter = _ConverterMeta._to_proto[binding]
        except KeyError:
            raise NotImplementedError
        else:
            return converter(obj, pytype=pytype)
    except NotImplementedError:
        # Either there's no converter or a converter has failed.
        raise TypeError(
            f'unable to encode outgoing TypedData: '
            f'unsupported type "{binding}" for '
            f'Python type "{type(obj).__name__}"')
