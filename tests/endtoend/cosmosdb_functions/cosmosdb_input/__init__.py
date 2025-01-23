# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(req: func.HttpRequest, docs_snake: func.DocumentList) -> str:
    return func.HttpResponse(docs_snake[0].to_json(), mimetype='application/json')
