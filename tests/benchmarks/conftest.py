# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import pytest_asyncio
import pytest
from azure_functions_worker.testutils import TESTS_ROOT


@pytest.fixture()
def save_profile(request):
    def _save_profile(profiler):
        (TESTS_ROOT / "benchmarks" / ".profiles").mkdir(exist_ok=True)
        results_file = TESTS_ROOT / "benchmarks" / ".profiles" / f"{request.node.name}.html"
        with open(results_file, "w", encoding="utf-8") as f:
            f.write(profiler.output_html())
    return _save_profile


@pytest_asyncio.fixture
async def aio_benchmark(benchmark, event_loop):
    def _wrapper(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            @benchmark
            def _():
                return event_loop.run_until_complete(func(*args, **kwargs))
        else:
            benchmark(func, *args, **kwargs)

    return _wrapper
