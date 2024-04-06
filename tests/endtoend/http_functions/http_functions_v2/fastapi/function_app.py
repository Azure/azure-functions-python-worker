# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from datetime import datetime
import logging
import time

import azure.functions as func
from azure.functions.extension.fastapi import Request, Response, \
    StreamingResponse, HTMLResponse, \
    UJSONResponse, ORJSONResponse, FileResponse

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


@app.route(route="upload_data_stream")
async def upload_data_stream(req: Request) -> Response:
    # Define a list to accumulate the streaming data
    data_chunks = []

    async def process_stream():
        async for chunk in req.stream():
            # Append each chunk of streaming data to the list
            data_chunks.append(chunk)

    await process_stream()

    # Concatenate the data chunks to form the complete data
    complete_data = b"".join(data_chunks)

    # Return the complete data as the response
    return Response(content=complete_data, status_code=200)


@app.route(route="return_streaming")
async def return_streaming(req: Request) -> StreamingResponse:
    async def content():
        yield b"First chunk\n"
        yield b"Second chunk\n"
    return StreamingResponse(content())


@app.route(route="return_html")
def return_html(req: Request) -> HTMLResponse:
    html_content = "<html><body><h1>Hello, World!</h1></body></html>"
    return HTMLResponse(content=html_content, status_code=200)


@app.route(route="return_ujson")
def return_ujson(req: Request) -> UJSONResponse:
    return UJSONResponse(content={"message": "Hello, World!"}, status_code=200)


@app.route(route="return_orjson")
def return_orjson(req: Request) -> ORJSONResponse:
    return ORJSONResponse(content={"message": "Hello, World!"}, status_code=200)


@app.route(route="return_file")
def return_file(req: Request) -> FileResponse:
    return FileResponse("function_app.py")
