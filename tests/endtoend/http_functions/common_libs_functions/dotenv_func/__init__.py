# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import azure.functions as func
from dotenv import load_dotenv
from pathlib import Path
import os


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    load_dotenv()
    env_path = Path('.') / '.env'
    load_dotenv(dotenv_path=env_path)

    domain = os.getenv("DOMAIN")
    email = os.getenv("EMAIL")

    res = "domain: {}, email: {}".format(domain, email)

    return func.HttpResponse(res)
