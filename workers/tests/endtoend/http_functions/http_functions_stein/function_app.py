# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import logging
import time

from datetime import datetime
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


@app.route(route="default_template")
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


@app.route(route="http_func")
def http_func(req: func.HttpRequest) -> func.HttpResponse:
    time.sleep(1)

    current_time = datetime.now().strftime("%H:%M:%S")
    return func.HttpResponse(f"{current_time}")


@app.route(route="custom_response")
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
