# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import azure.functions as func


def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    result = {
        'function_directory': context.function_directory,
        'function_name': context.function_name
    }
    return func.HttpResponse(body=json.dumps(result),
                             mimetype='application/json')
