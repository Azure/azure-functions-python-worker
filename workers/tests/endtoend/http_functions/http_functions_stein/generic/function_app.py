# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import logging

from typing import Generic, Mapping, Optional, TypeVar, Union

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


JsonType = Union[list, tuple, dict, str, int, float, bool]
T = TypeVar("T", bound=JsonType)


class JsonResponse(Generic[T], func.HttpResponse):
    def __init__(
        self,
        body: T,
        status_code: int = 200,
        headers: Optional[Mapping[str, str]] = None,
    ):
        super().__init__(json.dumps(body),
                         status_code=status_code,
                         headers=headers,
                         charset="utf-8")


@app.function_name(name="default_template")
@app.generic_trigger(arg_name="req",
                     type="httpTrigger",
                     route="default_template")
@app.generic_output_binding(arg_name="$return", type="http")
def default_template(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(
            f"Hello, {name}. This HTTP triggered function "
            f"executed successfully.")
    else:
        return func.HttpResponse(
            "This HTTP triggered function executed successfully. "
            "Pass a name in the query string or in the request body for a"
            " personalized response.",
            status_code=200
        )


@app.generic_trigger(arg_name="req",
                     type="httpTrigger",
                     route="custom_response")
@app.generic_output_binding(arg_name="$return", type="http")
def custom_response(req: func.HttpRequest) -> JsonResponse:
    name = req.params.get('name')
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')
    if name:
        return JsonResponse(
            {
                "name": name
            },
        )
    else:
        return JsonResponse(
            {
                "status": "healthy"
            },
        )
