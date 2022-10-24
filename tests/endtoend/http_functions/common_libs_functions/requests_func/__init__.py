# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import azure.functions as func
import requests


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    req = requests.get('https://github.com')
    res = "req status code: {}".format(req.status_code)

    return func.HttpResponse(res)
