# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import logging

import azure.functions


logger = logging.getLogger('my function')


async def main(req: azure.functions.HttpRequest):
    logger.info('hello %s', 'info')

    await asyncio.sleep(0.1)

    # Create a nested task to check if invocation_id is still
    # logged correctly.
    await asyncio.ensure_future(nested())

    await asyncio.sleep(0.1)

    return 'OK-async'


async def nested():
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('and another error', exc_info=True)
