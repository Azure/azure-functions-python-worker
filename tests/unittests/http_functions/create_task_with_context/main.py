# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import contextvars

import azure.functions

num = contextvars.ContextVar('num')
num.set(5)
ctx = contextvars.copy_context()


async def count(name: str):
    for i in range(ctx[num]):
        await asyncio.sleep(0.5)
    return f"Finished {name} in {ctx[num]}"


async def main(req: azure.functions.HttpRequest):
    count_task = asyncio.create_task(count("Hello World"), context=ctx)
    count_val = await count_task
    return f'{count_val}'
