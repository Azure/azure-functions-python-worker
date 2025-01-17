# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="jsut_double_underscore")
def jsut_double_underscore(__: func.HttpRequest) -> func.HttpResponse:
    name = __.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")