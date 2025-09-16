# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="classic_snake_case", trigger_arg_name="req_snake_snake_snake_snake")
def classic_snake_case(req_snake_snake_snake_snake: func.HttpRequest)\
        -> func.HttpResponse:
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


@app.route(route="underscore_prefix_snake", trigger_arg_name="_req_snake")
def underscore_prefix_snake(_req_snake: func.HttpRequest) -> func.HttpResponse:
    name = _req_snake.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="underscore_suffix", trigger_arg_name="req_")
def underscore_suffix(req_: func.HttpRequest) -> func.HttpResponse:
    name = req_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="underscore_suffix_snake", trigger_arg_name="req_snake_")
def underscore_suffix_snake(req_snake_: func.HttpRequest) -> func.HttpResponse:
    name = req_snake_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="ultimate_combo", trigger_arg_name="_req_snake_snake_snake_snake_")
def ultimate_combo(_req_snake_snake_snake_snake_: func.HttpRequest)\
        -> func.HttpResponse:
    name = _req_snake_snake_snake_snake_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="sandwich", trigger_arg_name="_req_")
def sandwich(_req_: func.HttpRequest)\
        -> func.HttpResponse:
    name = _req_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="double_underscore", trigger_arg_name="req__snake")
def double_underscore(req__snake: func.HttpRequest) -> func.HttpResponse:
    name = req__snake.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="double_underscore_prefix", trigger_arg_name="__req")
def classic_double_underscore(__req: func.HttpRequest) -> func.HttpResponse:
    name = __req.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="double_underscore_suffix", trigger_arg_name="req__")
def double_underscore_suffix(req__: func.HttpRequest) -> func.HttpResponse:
    name = req__.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="just_double_underscore", trigger_arg_name="__")
def just_double_underscore(__: func.HttpRequest) -> func.HttpResponse:
    name = __.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="python_main_keyword", trigger_arg_name="__main__")
def python_main_keyword(__main__: func.HttpRequest) -> func.HttpResponse:
    name = __main__.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")


@app.route(route="ultimate_combo2",
           trigger_arg_name="__9req__snake__sna_ke________snake__sn0ke_")
def ultimate_combo2(
        __9req__snake__sna_ke________snake__sn0ke_: func.HttpRequest)\
        -> func.HttpResponse:
    name = __9req__snake__sna_ke________snake__sn0ke_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
