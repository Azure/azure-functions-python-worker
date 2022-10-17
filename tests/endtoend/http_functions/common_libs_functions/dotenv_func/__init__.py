# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import azure.functions as func
from dotenv import load_dotenv
import os


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    load_dotenv()

    domain = os.getenv("DOMAIN")
    email = os.getenv("EMAIL")

    res = "domain: {}, email: {}".format(domain, email)

    return func.HttpResponse(res)
