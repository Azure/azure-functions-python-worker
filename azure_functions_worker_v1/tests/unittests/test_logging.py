# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import unittest

from azure_functions_worker_v1.logging import format_exception


class TestLogging(unittest.TestCase):

    def test_format_exception(self):
        def call0(fn):
            call1(fn)

        def call1(fn):
            call2(fn)

        def call2(fn):
            fn()

        def raising_function():
            raise ValueError("Value error being raised.", )

        try:
            call0(raising_function)
        except ValueError as e:
            processed_exception = format_exception(e)
            self.assertIn("call0", processed_exception)
            self.assertIn("call1", processed_exception)
            self.assertIn("call2", processed_exception)
            self.assertIn("f", processed_exception)
            self.assertRegex(processed_exception,
                             r".*tests\\unittests\\test_logging.py.*")
