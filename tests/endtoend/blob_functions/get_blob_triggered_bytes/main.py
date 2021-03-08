# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as azf


def main(req: azf.HttpRequest, file: str) -> azf.HttpResponse:
    """
    Read the given file (assumed to be in JSON format) and respond back with its
    content in the HTTP response.
    """
    return azf.HttpResponse(
        body=file,
        mimetype="application/json",
        status_code=200
    )
