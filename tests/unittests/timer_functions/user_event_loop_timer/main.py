# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import asyncio

import azure.functions as func


logger = logging.getLogger('my function')


async def try_log():
    logger.info("try_log")


def main(timer: func.TimerRequest):
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(try_log())
    loop.close()
