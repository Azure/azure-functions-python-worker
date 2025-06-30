# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json

import azure.functions as func


def main(req: func.HttpRequest, r: func.Out[func.SqlRow]) -> func.HttpResponse:
    body = json.loads(req.get_body())
    row = func.SqlRow.from_dict(body)
    r.set(row)

    return func.HttpResponse(
        body=req.get_body(),
        status_code=201,
        mimetype="application/json"
    )
