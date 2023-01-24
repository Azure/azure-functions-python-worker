# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import external_lib
from blueprint.blueprint import bp

app = func.FunctionApp()
app.register_functions(bp)


@app.route(route="default_template")
def default_template(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    external_lib.ExternalLib()

    return func.HttpResponse('ok')
