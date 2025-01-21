# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="double_underscore_prefix", trigger_arg_name="__req")
def classic_double_underscore(__req: func.HttpRequest) -> func.HttpResponse:
    name = __req.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")