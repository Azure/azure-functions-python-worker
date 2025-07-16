# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging
import threading

import azure.functions as func


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info('Before threads.')

    t1 = threading.Thread(target=thread_function, args=(context, 'Thread1 used.'))
    t2 = threading.Thread(target=thread_function, args=(context, 'Thread2 used.'))
    t3 = threading.Thread(target=thread_function, args=(context, 'Thread3 used.'))

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    logging.info('After threads.')

    return func.HttpResponse('This HTTP triggered function executed successfully.', status_code=200)


def thread_function(context: func.Context, message: str):
    context.thread_local_storage.invocation_id = context.invocation_id
    logging.info(message)
