# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions as func


def main(req: func.HttpRequest):
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie", 'foo=bar')

    return resp
