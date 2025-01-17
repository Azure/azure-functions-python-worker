# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="classic_snake_case")
def classic_snake_case(req_snake: func.HttpRequest) -> func.HttpResponse:
    name = req_snake.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")

@app.route(route="single_underscore")
def single_underscore(_: func.HttpRequest) -> func.HttpResponse:
    name = _.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")

@app.route(route="underscore_prefix")
def underscore_prefix(_req: func.HttpRequest) -> func.HttpResponse:
    name = _req.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")

@app.route(route="underscore_sufffix")
def underscore_sufffix(req_: func.HttpRequest) -> func.HttpResponse:
    name = req_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
