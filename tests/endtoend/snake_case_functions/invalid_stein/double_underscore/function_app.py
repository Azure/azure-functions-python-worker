# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="double_underscore", trigger_arg_name="req__snake")
def double_underscore(req__snake: func.HttpRequest) -> func.HttpResponse:
    name = req__snake.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")