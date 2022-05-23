# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import pytest

import azure_functions_worker.loader as loader
from azure.functions import Function
from azure.functions.decorators.core import InputBinding


def dummy_func():
    ...


class FakeInputBinding(InputBinding):

    def __init__(self,
                name):
        super().__init__(name=name, data_type=None)

    @staticmethod
    def get_binding_name() -> str:
        return "test_binding"


@pytest.mark.parametrize("size", range(10))
def test_build_binding_protos(benchmark, size):
    f = Function(dummy_func, "foo.py")
    for i in range(size):
        f.add_binding(FakeInputBinding(f"test_binding{i}"))
    r = benchmark(loader.build_binding_protos, f)
