# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import contextvars

import azure.functions

num = contextvars.ContextVar('num')


async def count(name: str):
    # The number of times the loop is executed
    # depends on the val set in context
    val = num.get()
    for i in range(val):
        await asyncio.sleep(0.5)
    return f"Finished {name} in {val}"


async def main(req: azure.functions.HttpRequest):
    # Create first task with context num = 5
    num.set(5)
    first_ctx = contextvars.copy_context()
    first_count_task = asyncio.create_task(count("Hello World"), context=first_ctx)

    # Create second task with context num = 10
    num.set(10)
    second_ctx = contextvars.copy_context()
    second_count_task = asyncio.create_task(count("Hello World"), context=second_ctx)

    # Execute tasks
    first_count_val = await first_count_task
    second_count_val = await second_count_task

    return f'{first_count_val + " | " + second_count_val}'
