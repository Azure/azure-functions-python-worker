# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import dotenv


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    res = "found" if "load_dotenv" in dotenv.__all__ else "not found"

    return func.HttpResponse(res)
