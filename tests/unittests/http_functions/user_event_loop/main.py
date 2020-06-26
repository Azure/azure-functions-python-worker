# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import asyncio

import azure.functions as func


logger = logging.getLogger('my function')


async def try_log():
    logger.info("try_log")


def main(req: func.HttpRequest) -> func.HttpResponse:
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)

    # This line should throws an asyncio RuntimeError exception
    loop.run_until_complete(try_log())
    loop.close()
    return 'OK-user-event-loop'
