# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import unittest

from azure.functions import Function
from azure.functions.decorators.blob import BlobInput
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

    def test_add_indexed_function_invalid_direction(self):
        trigger1 = HttpTrigger(name="req1", route="test")
        binding = BlobInput(name="$return", path="testpath",
                            connection="testconnection")
        self.func.add_trigger(trigger=trigger1)
        self.func.add_binding(binding=binding)

        with self.assertRaises(FunctionLoadError) as ex:
            self.function_registry.add_indexed_function(function=self.func)

        self.assertEqual(str(ex.exception),
                         'cannot load the dummy function: \"$return\" '
                         'binding must have direction set to \"out\"')
