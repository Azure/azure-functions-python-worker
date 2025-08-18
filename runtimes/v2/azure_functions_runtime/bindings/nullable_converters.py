# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys

from datetime import datetime
from typing import Optional, Union


def to_nullable_string(nullable: Optional[str], property_name: str, protos):
    """Converts string input to an 'NullableString' to be sent through the
    RPC layer. Input that is not a string but is also not null or undefined
    logs a function app level warning.

    :param nullable Input to be converted to an NullableString if it is a
    valid string
    :param property_name The name of the property that the caller will
    assign the output to. Used for debugging.
    :param: protos The protos object used for returning the appropriate value
    """
    if isinstance(nullable, str):
        return protos.NullableString(value=nullable)

    if nullable is not None:
        raise TypeError(
            "A 'str' type was expected instead of a '%s' "
            "type. Cannot parse value %s of '%s'."
            % (type(nullable), nullable, property_name))

    return None


def to_nullable_bool(nullable: Optional[bool], property_name: str, protos):
    """Converts boolean input to an 'NullableBool' to be sent through the
    RPC layer. Input that is not a boolean but is also not null or undefined
    logs a function app level warning.

    :param nullable Input to be converted to an NullableBool if it is a
    valid boolean
    :param property_name The name of the property that the caller will
    assign the output to. Used for debugging.
    :param protos The protos object used for returning the appropriate value
    """
    if isinstance(nullable, bool):
        return protos.NullableBool(value=nullable)

    if nullable is not None:
        raise TypeError(
            "A 'bool' type was expected instead of a '%s' "
            "type. Cannot parse value %s of '%s'."
            % (type(nullable), nullable, property_name))

    return None


def to_nullable_double(nullable: Optional[Union[str, int, float]],
                       property_name: str, protos):
    """Converts int or float or str that parses to a number to an
    'NullableDouble' to be sent through the RPC layer. Input that is not a
    valid number but is also not null or undefined logs a function app level
    warning.
    :param nullable Input to be converted to an NullableDouble if it is a
    valid number
    :param property_name The name of the property that the caller will
    assign the output to. Used for debugging.
    :param protos The protos object used for returning the appropriate value
    """
    if isinstance(nullable, int) or isinstance(nullable, float):
        return protos.NullableDouble(value=nullable)
    elif isinstance(nullable, str):
        if len(nullable) == 0:
            return None

        try:
            return protos.NullableDouble(value=float(nullable))
        except Exception:
            raise TypeError(
                "Cannot parse value %s of '%s' to "
                "float." % (nullable, property_name))

    if nullable is not None:
        raise TypeError(
            "A 'int' or 'float'"
            " type was expected instead of a '%s' "
            "type. Cannot parse value %s of '%s'."
            % (type(nullable), nullable, property_name))

    return None


def to_nullable_timestamp(date_time: Optional[Union[datetime, int]],
                          property_name: str, protos):
    """Converts Date or number input to an 'NullableTimestamp' to be sent
    through the RPC layer. Input that is not a Date or number but is also
    not null or undefined logs a function app level warning.

    :param date_time Input to be converted to an NullableTimestamp if it is
    valid input
    :param property_name The name of the property that the caller will
    assign the output to. Used for debugging.
    :param protos The protos object used for returning the appropriate value
    """
    if date_time is not None:
        try:
            time_in_seconds = date_time if isinstance(date_time,
                                                      int) else \
                date_time.timestamp()

            try:
                from google.protobuf.timestamp_pb2 import Timestamp
            except ImportError:
                raise ImportError(
                    "protobuf not found when trying to "
                    "import Timestamp."
                    "Sys Path: %s. "
                    "Sys Modules: %s. ",
                    sys.path, sys.modules)

            return protos.NullableTimestamp(
                value=Timestamp(seconds=int(time_in_seconds)))
        except Exception:
            raise TypeError(
                "A 'datetime' or 'int'"
                " type was expected instead of a '%s' "
                "type. Cannot parse value %s of '%s'."
                % (type(date_time), date_time, property_name))
    return None
