# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging
import concurrent.futures

import azure.functions as func


async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info('Before TPE.')

    with concurrent.futures.ThreadPoolExecutor() as tpe:
        tpe.submit(thread_function, context, 'Using TPE.')

    logging.info('After TPE.')

    return func.HttpResponse('This HTTP triggered function executed successfully.', status_code=200)


def thread_function(context: func.Context, message: str):
    context.thread_local_storage.invocation_id = context.invocation_id
    logging.info(message)
