# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import unittest
from azure.functions import Function
from azure.functions.decorators.http import HttpTrigger

from azure_functions_worker import functions
from azure_functions_worker.functions import FunctionLoadError


class TestFunctionsRegistry(unittest.TestCase):

    def setUp(self) -> None:
        def dummy():
            return "test"

        self.dummy = dummy
        self.func = Function(self.dummy, "test.py")
        self.function_registry = functions.Registry()

    def test_add_index_functions_invalid_route(self):
        function_id = '123'

        trigger1 = HttpTrigger(name="req1",
                               route="/")
        self.func.add_trigger(trigger=trigger1)

        with self.assertRaises(FunctionLoadError):
            self.function_registry.add_indexed_function(function_id,
                                                        self.func)
