# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from datetime import datetime
import logging
import time

import azure.functions as func

from azure.functions.extension.fastapi import Request, Response, StreamingResponse, \
    HTMLResponse, PlainTextResponse, HTMLResponse, JSONResponse, \
    UJSONResponse, ORJSONResponse, RedirectResponse, FileResponse

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="default_template")
async def default_template(req: Request) -> Response:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.query_params.get('name')
    if not name:
        try:
            req_body = await req.json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return Response(
            f"Hello, {name}. This HTTP triggered function "
            f"executed successfully.")
    else:
        return Response(
            "This HTTP triggered function executed successfully. "
            "Pass a name in the query string or in the request body for a"
            " personalized response.",
            status_code=200
        )


@app.route(route="http_func")
def http_func(req: Request) -> Response:
    time.sleep(1)

    current_time = datetime.now().strftime("%H:%M:%S")
    return Response(f"{current_time}")
