# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import hashlib
import logging
import sys
import time
from datetime import datetime
from pydantic import BaseModel
from urllib.request import urlopen

import azure.functions as func
from azurefunctions.extensions.http.fastapi import (
    FileResponse,
    HTMLResponse,
    ORJSONResponse,
    RedirectResponse,
    Request,
    Response,
    StreamingResponse,
    UJSONResponse,
)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

logger = logging.getLogger("my-function")


class Item(BaseModel):
    name: str
    description: str


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


@app.route(route="no_type_hint")
def no_type_hint(req):
    return 'no_type_hint'


@app.route(route="return_int")
def return_int(req) -> int:
    return 1000


@app.route(route="return_float")
def return_float(req) -> float:
    return 1000.0


@app.route(route="return_bool")
def return_bool(req) -> bool:
    return True


@app.route(route="return_dict")
def return_dict(req) -> dict:
    return {"key": "value"}


@app.route(route="return_list")
def return_list(req):
    return ["value1", "value2"]


@app.route(route="return_pydantic_model")
def return_pydantic_model(req) -> Item:
    item = Item(name="item1", description="description1")
    return item


@app.route(route="return_pydantic_model_with_missing_fields")
def return_pydantic_model_with_missing_fields(req) -> Item:
    item = Item(name="item1")
    return item


@app.route(route="accept_json")
async def accept_json(req: Request):
    return await req.json()


async def nested():
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('and another error', exc_info=True)


@app.route(route="async_logging")
async def async_logging(req: Request):
    logger.info('hello %s', 'info')

    await asyncio.sleep(0.1)

    # Create a nested task to check if invocation_id is still
    # logged correctly.
    await asyncio.ensure_future(nested())

    await asyncio.sleep(0.1)

    return 'OK-async'


@app.route(route="async_return_str")
async def async_return_str(req: Request):
    await asyncio.sleep(0.1)
    return 'Hello Async World!'


@app.route(route="debug_logging")
def debug_logging(req: Request):
    logging.critical('logging critical', exc_info=True)
    logging.info('logging info', exc_info=True)
    logging.warning('logging warning', exc_info=True)
    logging.debug('logging debug', exc_info=True)
    logging.error('logging error', exc_info=True)
    return 'OK-debug'


@app.route(route="debug_user_logging")
def debug_user_logging(req: Request):
    logger.setLevel(logging.DEBUG)

    logging.critical('logging critical', exc_info=True)
    logger.info('logging info', exc_info=True)
    logger.warning('logging warning', exc_info=True)
    logger.debug('logging debug', exc_info=True)
    logger.error('logging error', exc_info=True)
    return 'OK-user-debug'


# Attempt to log info into system log from customer code
disguised_logger = logging.getLogger('azure_functions_worker')


async def parallelly_print():
    await asyncio.sleep(0.1)
    print('parallelly_print')


async def parallelly_log_info():
    await asyncio.sleep(0.2)
    logging.info('parallelly_log_info at root logger')


async def parallelly_log_warning():
    await asyncio.sleep(0.3)
    logging.warning('parallelly_log_warning at root logger')


async def parallelly_log_error():
    await asyncio.sleep(0.4)
    logging.error('parallelly_log_error at root logger')


async def parallelly_log_exception():
    await asyncio.sleep(0.5)
    try:
        raise Exception('custom exception')
    except Exception:
        logging.exception('parallelly_log_exception at root logger',
                          exc_info=sys.exc_info())


async def parallelly_log_custom():
    await asyncio.sleep(0.6)
    logger.info('parallelly_log_custom at custom_logger')


async def parallelly_log_system():
    await asyncio.sleep(0.7)
    disguised_logger.info('parallelly_log_system at disguised_logger')


@app.route(route="hijack_current_event_loop")
async def hijack_current_event_loop(req: Request) -> Response:
    loop = asyncio.get_event_loop()

    # Create multiple tasks and schedule it into one asyncio.wait blocker
    task_print: asyncio.Task = loop.create_task(parallelly_print())
    task_info: asyncio.Task = loop.create_task(parallelly_log_info())
    task_warning: asyncio.Task = loop.create_task(parallelly_log_warning())
    task_error: asyncio.Task = loop.create_task(parallelly_log_error())
    task_exception: asyncio.Task = loop.create_task(parallelly_log_exception())
    task_custom: asyncio.Task = loop.create_task(parallelly_log_custom())
    task_disguise: asyncio.Task = loop.create_task(parallelly_log_system())

    # Create an awaitable future and occupy the current event loop resource
    future = loop.create_future()
    loop.call_soon_threadsafe(future.set_result, 'callsoon_log')

    # WaitAll
    await asyncio.wait([task_print, task_info, task_warning, task_error,
                        task_exception, task_custom, task_disguise, future])

    # Log asyncio low-level future result
    logging.info(future.result())

    return 'OK-hijack-current-event-loop'


@app.route(route="print_logging")
def print_logging(req: Request):
    flush_required = False
    is_console_log = False
    is_stderr = False
    message = req.query_params.get('message', '')

    if req.query_params.get('flush') == 'true':
        flush_required = True
    if req.query_params.get('console') == 'true':
        is_console_log = True
    if req.query_params.get('is_stderr') == 'true':
        is_stderr = True

    # Adding LanguageWorkerConsoleLog will make function host to treat
    # this as system log and will be propagated to kusto
    prefix = 'LanguageWorkerConsoleLog' if is_console_log else ''
    print(f'{prefix} {message}'.strip(),
          file=sys.stderr if is_stderr else sys.stdout,
          flush=flush_required)

    return 'OK-print-logging'


@app.route(route="raw_body_bytes")
async def raw_body_bytes(req: Request) -> Response:
    body = await req.body()
    body_len = str(len(body))

    headers = {'body-len': body_len}
    return Response(content=body, status_code=200, headers=headers)


@app.route(route="remapped_context")
def remapped_context(req: Request):
    return req.method


@app.route(route="return_bytes")
def return_bytes(req: Request):
    return b"Hello World"


@app.route(route="return_context")
def return_context(req: Request, context: func.Context):
    return {
        'method': req.method,
        'ctx_func_name': context.function_name,
        'ctx_func_dir': context.function_directory,
        'ctx_invocation_id': context.invocation_id,
        'ctx_trace_context_Traceparent': context.trace_context.Traceparent,
        'ctx_trace_context_Tracestate': context.trace_context.Tracestate,
    }


@app.route(route="return_http")
def return_http(req: Request) -> HTMLResponse:
    return HTMLResponse('<h1>Hello World™</h1>')


@app.route(route="return_http_404")
def return_http_404(req: Request):
    return Response('bye', status_code=404)


@app.route(route="return_http_auth_admin", auth_level=func.AuthLevel.ADMIN)
def return_http_auth_admin(req: Request) -> HTMLResponse:
    return HTMLResponse('<h1>Hello World™</h1>')


@app.route(route="return_http_no_body")
def return_http_no_body(req: Request):
    return Response()


@app.route(route="return_http_redirect")
def return_http_redirect(req: Request):
    return RedirectResponse(url='/api/return_http', status_code=302)


@app.route(route="return_request")
async def return_request(req: Request):
    params = dict(req.query_params)
    params.pop('code', None)  # Remove 'code' parameter if present

    # Get the body content and calculate its hash
    body = await req.body()
    body_hash = hashlib.sha256(body).hexdigest() if body else None

    # Return a dictionary containing request information
    return {
        'method': req.method,
        'url': str(req.url),
        'headers': dict(req.headers),
        'params': params,
        'body': body.decode() if body else None,
        'body_hash': body_hash,
    }


@app.route(route="return_route_params/{param1}/{param2}")
def return_route_params(req: Request) -> str:
    # log type of req
    logger.info(f"req type: {type(req)}")
    # log req path params
    logger.info(f"req path params: {req.path_params}")
    return req.path_params


@app.route(route="sync_logging")
def main(req: Request):
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('a gracefully handled error', exc_info=True)
        logger.error('a gracefully handled critical error', exc_info=True)
    time.sleep(0.05)
    return 'OK-sync'


@app.route(route="unhandled_error")
def unhandled_error(req: Request):
    1 / 0


@app.route(route="unhandled_urllib_error")
def unhandled_urllib_error(req: Request) -> str:
    image_url = req.params.get('img')
    urlopen(image_url).read()


class UnserializableException(Exception):
    def __str__(self):
        raise RuntimeError('cannot serialize me')


@app.route(route="unhandled_unserializable_error")
def unhandled_unserializable_error(req: Request) -> str:
    raise UnserializableException('foo')


async def try_log():
    logger.info("try_log")


@app.route(route="user_event_loop")
def user_event_loop(req: Request) -> Response:
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)

    # This line should throws an asyncio RuntimeError exception
    loop.run_until_complete(try_log())
    loop.close()
    return 'OK-user-event-loop'


@app.route(route="multiple_set_cookie_resp_headers")
async def multiple_set_cookie_resp_headers(req: Request):
    logging.info('Python HTTP trigger function processed a request.')
    resp = Response(
        "This HTTP triggered function executed successfully.")

    expires_1 = "Thu, 12 Jan 2017 13:55:08 GMT"
    expires_2 = "Fri, 12 Jan 2018 13:55:08 GMT"

    resp.set_cookie(
        key='foo3',
        value='42',
        domain='example.com',
        expires=expires_1,
        path='/',
        max_age=10000000,
        secure=True,
        httponly=True,
        samesite='Lax'
    )

    resp.set_cookie(
        key='foo3',
        value='43',
        domain='example.com',
        expires=expires_2,
        path='/',
        max_age=10000000,
        secure=True,
        httponly=True,
        samesite='Lax'
    )

    return resp


@app.route(route="response_cookie_header_nullable_bool_err")
def response_cookie_header_nullable_bool_err(
        req: Request) -> Response:
    logging.info('Python HTTP trigger function processed a request.')
    resp = Response(
        "This HTTP triggered function executed successfully.")

    # Set the cookie with Secure attribute set to False
    resp.set_cookie(
        key='foo3',
        value='42',
        domain='example.com',
        expires='Thu, 12-Jan-2017 13:55:08 GMT',
        path='/',
        max_age=10000000,
        secure=False,
        httponly=True
    )

    return resp


@app.route(route="response_cookie_header_nullable_timestamp_err")
def response_cookie_header_nullable_timestamp_err(
        req: Request) -> Response:
    logging.info('Python HTTP trigger function processed a request.')
    resp = Response(
        "This HTTP triggered function executed successfully.")

    resp.set_cookie(
        key='foo3',
        value='42',
        domain='example.com'
    )

    return resp


@app.route(route="set_cookie_resp_header_default_values")
def set_cookie_resp_header_default_values(
        req: Request) -> Response:
    logging.info('Python HTTP trigger function processed a request.')
    resp = Response(
        "This HTTP triggered function executed successfully.")

    resp.set_cookie(
        key='foo3',
        value='42'
    )

    return resp
