# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body()
    body_len = str(len(body))

    headers = {'body-len': body_len}
    return func.HttpResponse(body=body, status_code=200, headers=headers)
