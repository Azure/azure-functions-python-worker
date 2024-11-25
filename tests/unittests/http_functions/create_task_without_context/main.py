# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio

import azure.functions


async def count(name: str, num: int):
    # The number of times the loop executes is decided by a
    # user-defined param
    for i in range(num):
        await asyncio.sleep(0.5)
    return f"Finished {name} in {num}"


async def main(req: azure.functions.HttpRequest):
    # No context is being sent into asyncio.create_task
    count_task = asyncio.create_task(count("Hello World", 5))
    count_val = await count_task
    return f'{count_val}'
