# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="python_main_keyword", trigger_arg_name="__main__")
def python_main_keyword(__main__: func.HttpRequest) -> func.HttpResponse:
    name = __main__.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
