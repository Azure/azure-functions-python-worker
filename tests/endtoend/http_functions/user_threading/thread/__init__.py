# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging
import threading

import azure.functions as func


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    t1 = threading.Thread(target=thread_function, args=(context, "t1 success"))
    t2 = threading.Thread(target=thread_function, args=(context, "t2 success"))
    t3 = threading.Thread(target=thread_function, args=(context, "t1 success"))

    t1.start()
    t2.start()
    t3.start()

    return func.HttpResponse("This HTTP triggered function executed successfully.", status_code=200)


def thread_function(context: func.Context, message: int):
    context.local_thread.invocation_id = context.invocation_id
    logging.info(message)