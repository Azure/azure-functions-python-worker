# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import functools

from typing import Any

from ..otel import otel_manager, configure_opentelemetry


def get_current_loop():
    return asyncio.events.get_event_loop()


async def execute_async(function, args) -> Any:
    return await function(**args)


def execute_sync(function, args) -> Any:
    return function(**args)


def run_sync_func(invocation_id, context, func, params):
    # This helper exists because we need to access the current
    # invocation_id from ThreadPoolExecutor's threads.
    context.thread_local_storage.invocation_id = invocation_id
    try:
        if otel_manager.get_azure_monitor_available():
            configure_opentelemetry(context)
        result = functools.partial(execute_sync, func)
        return result(params)
    finally:
        context.thread_local_storage.invocation_id = None
