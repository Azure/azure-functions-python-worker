# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import pytest_asyncio


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
