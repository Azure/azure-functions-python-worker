# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import asyncio
import contextvars
import hashlib
import json
import logging
import sys
import time
from datetime import datetime
from urllib.request import urlopen

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

logger = logging.getLogger("my-function")
num = contextvars.ContextVar('num')


async def count_with_context(name: str):
    # The number of times the loop is executed
    # depends on the val set in context
    val = num.get()
    for i in range(val):
        await asyncio.sleep(0.5)
    return f"Finished {name} in {val}"


async def count_without_context(name: str, number: int):
    # The number of times the loop executes is decided by a
    # user-defined param
    for i in range(number):
        await asyncio.sleep(0.5)
    return f"Finished {name} in {number}"


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


@app.route(route="return_str")
def return_str(req: func.HttpRequest) -> str:
    return 'Hello World!'


@app.route(route="accept_json")
def accept_json(req: func.HttpRequest):
    return json.dumps({
        'method': req.method,
        'url': req.url,
        'headers': dict(req.headers),
        'params': dict(req.params),
        'get_body': req.get_body().decode(),
        'get_json': req.get_json()
    })


async def nested():
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('and another error', exc_info=True)


@app.route(route="async_logging")
async def async_logging(req: func.HttpRequest):
    logger.info('hello %s', 'info')

    await asyncio.sleep(0.1)

    # Create a nested task to check if invocation_id is still
    # logged correctly.
    await asyncio.ensure_future(nested())

    await asyncio.sleep(0.1)

    return 'OK-async'


@app.route(route="async_return_str")
async def async_return_str(req: func.HttpRequest):
    await asyncio.sleep(0.1)
    return 'Hello Async World!'


@app.route(route="debug_logging")
def debug_logging(req: func.HttpRequest):
    logging.critical('logging critical', exc_info=True)
    logging.info('logging info', exc_info=True)
    logging.warning('logging warning', exc_info=True)
    logging.debug('logging debug', exc_info=True)
    logging.error('logging error', exc_info=True)
    return 'OK-debug'


@app.route(route="debug_user_logging")
def debug_user_logging(req: func.HttpRequest):
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
async def hijack_current_event_loop(req: func.HttpRequest) -> func.HttpResponse:
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


@app.route(route="no_return")
def no_return(req: func.HttpRequest):
    logger.info('hi')


@app.route(route="no_return_returns")
def no_return_returns(req):
    return 'ABC'


@app.route(route="print_logging")
def print_logging(req: func.HttpRequest):
    flush_required = False
    is_console_log = False
    is_stderr = False
    message = req.params.get('message', '')

    if req.params.get('flush') == 'true':
        flush_required = True
    if req.params.get('console') == 'true':
        is_console_log = True
    if req.params.get('is_stderr') == 'true':
        is_stderr = True

    # Adding LanguageWorkerConsoleLog will make function host to treat
    # this as system log and will be propagated to kusto
    prefix = 'LanguageWorkerConsoleLog' if is_console_log else ''
    print(f'{prefix} {message}'.strip(),
          file=sys.stderr if is_stderr else sys.stdout,
          flush=flush_required)

    return 'OK-print-logging'


@app.route(route="raw_body_bytes")
def raw_body_bytes(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_body()
    body_len = str(len(body))

    headers = {'body-len': body_len}
    return func.HttpResponse(body=body, status_code=200, headers=headers)


@app.route(route="remapped_context")
def remapped_context(req: func.HttpRequest):
    return req.method


@app.route(route="return_bytes")
def return_bytes(req: func.HttpRequest):
    # This function will fail, as we don't auto-convert "bytes" to "http".
    return b'Hello World!'


@app.route(route="return_context")
def return_context(req: func.HttpRequest, context: func.Context):
    return json.dumps({
        'method': req.method,
        'ctx_func_name': context.function_name,
        'ctx_func_dir': context.function_directory,
        'ctx_invocation_id': context.invocation_id,
        'ctx_trace_context_Traceparent': context.trace_context.Traceparent,
        'ctx_trace_context_Tracestate': context.trace_context.Tracestate,
    })


@app.route(route="return_http")
def return_http(req: func.HttpRequest):
    return func.HttpResponse('<h1>Hello World™</h1>',
                             mimetype='text/html')


@app.route(route="return_http_404")
def return_http_404(req: func.HttpRequest):
    return func.HttpResponse('bye', status_code=404)


@app.route(route="return_http_auth_admin", auth_level=func.AuthLevel.ADMIN)
def return_http_auth_admin(req: func.HttpRequest):
    return func.HttpResponse('<h1>Hello World™</h1>',
                             mimetype='text/html')


@app.route(route="return_http_no_body")
def return_http_no_body(req: func.HttpRequest):
    return func.HttpResponse()


@app.route(route="return_http_redirect")
def return_http_redirect(req: func.HttpRequest):
    location = 'return_http?code={}'.format(req.params['code'])
    return func.HttpResponse(
        status_code=302,
        headers={'location': location})


@app.route(route="return_out", binding_arg_name="foo")
def return_out(req: func.HttpRequest, foo: func.Out[func.HttpResponse]):
    foo.set(func.HttpResponse(body='hello', status_code=201))


@app.route(route="return_request")
def return_request(req: func.HttpRequest):
    params = dict(req.params)
    params.pop('code', None)
    body = req.get_body()
    return json.dumps({
        'method': req.method,
        'url': req.url,
        'headers': dict(req.headers),
        'params': params,
        'get_body': body.decode(),
        'body_hash': hashlib.sha256(body).hexdigest(),
    })


@app.route(route="return_route_params/{param1}/{param2}")
def return_route_params(req: func.HttpRequest) -> str:
    return json.dumps(dict(req.route_params))


@app.route(route="sync_logging")
def main(req: func.HttpRequest):
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('a gracefully handled error', exc_info=True)
        logger.error('a gracefully handled critical error', exc_info=True)
    time.sleep(0.05)
    return 'OK-sync'


@app.route(route="unhandled_error")
def unhandled_error(req: func.HttpRequest):
    1 / 0


@app.route(route="unhandled_urllib_error")
def unhandled_urllib_error(req: func.HttpRequest) -> str:
    image_url = req.params.get('img')
    urlopen(image_url).read()


class UnserializableException(Exception):
    def __str__(self):
        raise RuntimeError('cannot serialize me')


@app.route(route="unhandled_unserializable_error")
def unhandled_unserializable_error(req: func.HttpRequest) -> str:
    raise UnserializableException('foo')


async def try_log():
    logger.info("try_log")


@app.route(route="user_event_loop")
def user_event_loop(req: func.HttpRequest) -> func.HttpResponse:
    loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(loop)

    # This line should throws an asyncio RuntimeError exception
    loop.run_until_complete(try_log())
    loop.close()
    return 'OK-user-event-loop'


@app.route(route="multiple_set_cookie_resp_headers")
def multiple_set_cookie_resp_headers(
        req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie",
                     'foo3=42; Domain=example.com; Expires=Thu, 12-Jan-2017 '
                     '13:55:08 GMT; Path=/; Max-Age=10000000; Secure; '
                     'HttpOnly')
    resp.headers.add("Set-Cookie",
                     'foo3=43; Domain=example.com; Expires=Thu, 12-Jan-2018 '
                     '13:55:08 GMT; Path=/; Max-Age=10000000; Secure; '
                     'HttpOnly')
    resp.headers.add("HELLO", 'world')

    return resp


@app.route(route="response_cookie_header_nullable_bool_err")
def response_cookie_header_nullable_bool_err(
        req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie",
                     'foo3=42; Domain=example.com; Expires=Thu, 12-Jan-2017 '
                     '13:55:08 GMT; Path=/; Max-Age=10000000; SecureFalse; '
                     'HttpOnly')

    return resp


@app.route(route="response_cookie_header_nullable_double_err")
def response_cookie_header_nullable_double_err(
        req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie",
                     'foo3=42; Domain=example.com; Expires=Thu, 12-Jan-2017 '
                     '13:55:08 GMT; Path=/; Max-Age=Dummy; SecureFalse; '
                     'HttpOnly')

    return resp


@app.route(route="response_cookie_header_nullable_timestamp_err")
def response_cookie_header_nullable_timestamp_err(
        req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie", 'foo=bar; Domain=123; Expires=Dummy')

    return resp


@app.route(route="set_cookie_resp_header_default_values")
def set_cookie_resp_header_default_values(
        req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie", 'foo=bar')

    return resp


@app.route(route="set_cookie_resp_header_empty")
def set_cookie_resp_header_empty(
        req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    resp = func.HttpResponse(
        "This HTTP triggered function executed successfully.")

    resp.headers.add("Set-Cookie", '')

    return resp


@app.route('create_task_with_context')
async def create_task_with_context(req: func.HttpRequest):
    # Create first task with context num = 5
    num.set(5)
    first_ctx = contextvars.copy_context()
    first_count_task = asyncio.create_task(
        count_with_context("Hello World"), context=first_ctx)

    # Create second task with context num = 10
    num.set(10)
    second_ctx = contextvars.copy_context()
    second_count_task = asyncio.create_task(
        count_with_context("Hello World"), context=second_ctx)

    # Execute tasks
    first_count_val = await first_count_task
    second_count_val = await second_count_task

    return f'{first_count_val + " | " + second_count_val}'


@app.route('create_task_without_context')
async def create_task_without_context(req: func.HttpRequest):
    # No context is being sent into asyncio.create_task
    count_task = asyncio.create_task(count_without_context("Hello World", 5))
    count_val = await count_task
    return f'{count_val}'
