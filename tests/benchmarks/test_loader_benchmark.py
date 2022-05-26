# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import pytest
from pyinstrument import Profiler

import azure_functions_worker.loader as loader
from azure_functions_worker.functions import Registry
from azure_functions_worker.testutils import TESTS_ROOT
from azure.functions import Function
from azure.functions.decorators.core import InputBinding


@pytest.fixture(autouse=True)
def profile(save_profile):
    # Turn profiling on
    profiler = Profiler(async_mode="enabled")
    profiler.start()

    yield  # Run test

    profiler.stop()
    save_profile(profiler)


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
    benchmark(loader.build_binding_protos, f)


def test_process_indexed_function(benchmark):
    def _test_func(test_binding0, test_binding1, test_binding2, test_binding3, test_binding4):
        pass

    f = Function(_test_func, "foo.py")
    for i in range(5):  # Use 5 bindings
        f.add_binding(FakeInputBinding(f"test_binding{i}"))
    reg = Registry()
    benchmark(loader.process_indexed_function, reg, [f, f, f, f, f])


def test_load_function(benchmark):
    loader.install()
    benchmark(
        loader.load_function,
        "http_functions",
        TESTS_ROOT / "benchmarks" / "dummy",
        TESTS_ROOT / "benchmarks" / "dummy" / "__init__.py",
        "foo"
    )
    loader.uninstall()


def test_index_function_app(benchmark):
    benchmark(
        loader.index_function_app,
        TESTS_ROOT / "benchmarks" / "dummy",
    )


def test_str_join(benchmark):
    def j(_input):
        return ", ".join([x for x in _input])
    
    benchmark(j, ["a", "b", "c", "d"])
