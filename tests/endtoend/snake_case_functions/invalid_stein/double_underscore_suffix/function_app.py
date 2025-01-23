# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="double_underscore_suffix", trigger_arg_name="req__")
def double_underscore_suffix(req__: func.HttpRequest) -> func.HttpResponse:
    name = req__.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
