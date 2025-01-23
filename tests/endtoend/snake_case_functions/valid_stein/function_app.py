# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="classic_snake_case", trigger_arg_name="req_snake_snake_snake_snake")
def classic_snake_case(req_snake_snake_snake_snake: func.HttpRequest) -> func.HttpResponse:
    name = req_snake_snake_snake_snake.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")

@app.route(route="single_underscore", trigger_arg_name="_")
def single_underscore(_: func.HttpRequest) -> func.HttpResponse:
    name = _.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")

@app.route(route="underscore_prefix", trigger_arg_name="_req")
def underscore_prefix(_req: func.HttpRequest) -> func.HttpResponse:
    name = _req.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")

@app.route(route="underscore_suffix", trigger_arg_name="req_")
def underscore_suffix(req_: func.HttpRequest) -> func.HttpResponse:
    name = req_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
