# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(req: func.HttpRequest, file: func.InputStream) -> str:
    return func.HttpResponse(body=file.read().decode('utf-8'),
                             status_code=200,
                             mimetype='application/json')
