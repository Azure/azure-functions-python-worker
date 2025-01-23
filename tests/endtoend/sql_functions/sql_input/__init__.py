# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json

import azure.functions as func


def main(req: func.HttpRequest, products_snake: func.SqlRowList) -> func.HttpResponse:
    rows = list(map(lambda r: json.loads(r.to_json()), products_snake))

    return func.HttpResponse(
        json.dumps(rows),
        status_code=200,
        mimetype="application/json"
    )
