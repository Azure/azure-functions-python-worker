# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import unittest
from collections import Callable
from typing import Optional, List

from azure_functions_worker import functions
from azure_functions_worker.functions import FunctionLoadError


def dummy_func():
    pass


class MockTrigger():
    def __init__(self, name: str):
        self.name = name


class MockBindings():
    def __init__(self, name: str,
                 direction: str,
                 data_type: str = None):
        self.name = name
        self._direction = direction
        self._data_type = data_type


class MockFunction:
    def __init__(self, name, func: Callable, trigger: MockTrigger,
                 binding: MockBindings,
                 script_file: str):
        """Constructor of :class:`FunctionBuilder` object.

        :param func: User defined python function instance.
        :param script_file: File name indexed by worker to find function.
        """
        self._name: str = name
        self._func = func
        self._trigger: trigger
        self._bindings: binding
        self.function_script_file = script_file

    def get_user_function(self):
        return self._func

    def get_function_name(self):
        return self._name


class TestFunctionsRegistry(unittest.TestCase):

    def setUp(self) -> None:
        self.function_registry = functions.Registry()

    def setup_test_function(self):
        mock_binding = MockBindings('test_binding', 'in')
        mock_trigger = MockTrigger('test_trigger')
        return MockFunction('test_function', dummy_func(), mock_trigger,
                            mock_binding, "file")

    def test_add_index_functions_invalid_route(self):
        function_id = '123'
        function = self.setup_test_function()
        with self.assertRaises(FunctionLoadError):
            self.function_registry.add_indexed_function(function_id,
                                                        function)
