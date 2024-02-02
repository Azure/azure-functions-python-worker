import datetime
import unittest

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from azure_functions_worker import protos
from azure_functions_worker.bindings.nullable_converters import (
    to_nullable_bool,
    to_nullable_double,
    to_nullable_string,
    to_nullable_timestamp,
)

try:
    from http.cookies import SimpleCookie
except ImportError:
    from Cookie import SimpleCookie

headers = [
    "foo=bar; Path=/some/path; Secure",
    "foo2=42; Domain=123; Expires=Thu, 12-Jan-2017 13:55:08 GMT; "
    "Path=/; Max-Age=dd;",
]

cookies = SimpleCookie("\r\n".join(headers))


class TestNullableConverters(unittest.TestCase):
    def test_to_nullable_string_none(self):
        self.assertEqual(to_nullable_string(None, "name"), None)

    def test_to_nullable_string_valid(self):
        self.assertEqual(
            to_nullable_string("dummy", "name"), protos.NullableString(value="dummy")
        )

    def test_to_nullable_string_wrong_type(self):
        with pytest.raises(Exception) as e:
            self.assertEqual(
                to_nullable_string(123, "name"), protos.NullableString(value="dummy")
            )
            self.assertEqual(type(e), TypeError)

    def test_to_nullable_bool_none(self):
        self.assertEqual(to_nullable_bool(None, "name"), None)

    def test_to_nullable_bool_valid(self):
        self.assertEqual(
            to_nullable_bool(True, "name"), protos.NullableBool(value=True)
        )

    def test_to_nullable_bool_wrong_type(self):
        with pytest.raises(Exception) as e:
            to_nullable_bool("True", "name")

        self.assertEqual(e.type, TypeError)
        self.assertEqual(
            e.value.args[0],
            "A 'bool' type was expected instead of a '<class "
            "'str'>' type. "
            "Cannot parse value True of 'name'.",
        )

    def test_to_nullable_double_str(self):
        self.assertEqual(
            to_nullable_double("12", "name"), protos.NullableDouble(value=12)
        )

    def test_to_nullable_double_empty_str(self):
        self.assertEqual(to_nullable_double("", "name"), None)

    def test_to_nullable_double_invalid_str(self):
        with pytest.raises(TypeError) as e:
            to_nullable_double("222d", "name")

        self.assertEqual(e.type, TypeError)
        self.assertEqual(e.value.args[0], "Cannot parse value 222d of 'name' to float.")

    def test_to_nullable_double_int(self):
        self.assertEqual(
            to_nullable_double(12, "name"), protos.NullableDouble(value=12)
        )

    def test_to_nullable_double_float(self):
        self.assertEqual(
            to_nullable_double(12.0, "name"), protos.NullableDouble(value=12)
        )

    def test_to_nullable_double_none(self):
        self.assertEqual(to_nullable_double(None, "name"), None)

    def test_to_nullable_double_wrong_type(self):
        with pytest.raises(Exception) as e:
            to_nullable_double(object(), "name")

        self.assertIn(
            "A 'int' or 'float' type was expected instead of a '<class "
            "'object'>' type",
            e.value.args[0],
        )
        self.assertEqual(e.type, TypeError)

    def test_to_nullable_timestamp_int(self):
        self.assertEqual(
            to_nullable_timestamp(1000, "datetime"),
            protos.NullableTimestamp(value=Timestamp(seconds=int(1000))),
        )

    def test_to_nullable_timestamp_datetime(self):
        now = datetime.datetime.now()
        self.assertEqual(
            to_nullable_timestamp(now, "datetime"),
            protos.NullableTimestamp(value=Timestamp(seconds=int(now.timestamp()))),
        )

    def test_to_nullable_timestamp_wrong_type(self):
        with self.assertRaises(TypeError):
            to_nullable_timestamp("now", "datetime")

    def test_to_nullable_timestamp_none(self):
        self.assertEqual(to_nullable_timestamp(None, "timestamp"), None)
