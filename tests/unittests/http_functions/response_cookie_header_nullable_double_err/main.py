# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions as func


def main(req: func.HttpRequest):
    logging.info("Python HTTP trigger function processed a request.")
    resp = func.HttpResponse("This HTTP triggered function executed successfully.")

    resp.headers.add(
        "Set-Cookie",
        "foo3=42; Domain=example.com; Expires=Thu, 12-Jan-2017 "
        "13:55:08 GMT; Path=/; Max-Age=Dummy; SecureFalse; "
        "HttpOnly",
    )

    return resp
