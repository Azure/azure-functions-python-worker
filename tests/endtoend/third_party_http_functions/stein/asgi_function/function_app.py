import asyncio
import logging
import sys

from typing import Optional
from urllib.request import urlopen

import azure.functions as func
from fastapi import Body, FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

fast_app = FastAPI()
logger = logging.getLogger("my-function")
# Attempt to log info into system log from customer code
disguised_logger = logging.getLogger('azure_functions_worker')


class Fruit(BaseModel):
    name: str
    description: Optional[str] = None


@fast_app.get("/get_query_param")
async def get_query_param(name: str = "world"):
    return Response(content=f"hello {name}", media_type="text/plain")


@fast_app.post("/post_str")
async def post_str(person: str = Body(...)):
    return Response(content=f"hello {person}", media_type="text/plain")


@fast_app.post("/post_json_return_json_response")
async def post_json_return_json_response(fruit: Fruit):
    return fruit


@fast_app.get("/get_path_param/{id}")
async def get_path_param(id):
    return Response(content=f"hello {id}", media_type="text/plain")


@fast_app.get("/raise_http_exception")
async def raise_http_exception():
    raise HTTPException(status_code=404, detail="Item not found")

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


@fast_app.get("/debug_logging")
async def debug_logging():
    logging.critical('logging critical', exc_info=True)
    logging.info('logging info', exc_info=True)
    logging.warning('logging warning', exc_info=True)
    logging.debug('logging debug', exc_info=True)
    logging.error('logging error', exc_info=True)

    return Response(content='OK-debug', media_type="text/plain")


@fast_app.get("/debug_user_logging")
async def debug_user_logging():
    logger.setLevel(logging.DEBUG)

    logger.critical('logging critical', exc_info=True)
    logger.info('logging info', exc_info=True)
    logger.warning('logging warning', exc_info=True)
    logger.debug('logging debug', exc_info=True)
    logger.error('logging error', exc_info=True)

    return Response(content='OK-user-debug', media_type="text/plain")


@fast_app.get("/hijack_current_event_loop")
async def hijack_current_event_loop():
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

    return Response(content='OK-hijack-current-event-loop',
                    media_type="text/plain")


@fast_app.get("/print_logging")
async def print_logging(message: str = "", flush: str = 'false',
                        console: str = 'false', is_stderr: str = 'false'):
    flush_required = False
    is_console_log = False
    is_stderr = False

    if flush == 'true':
        flush_required = True
    if console == 'true':
        is_console_log = True
    if is_stderr == 'true':
        is_stderr = True

    # Adding LanguageWorkerConsoleLog will make function host to treat
    # this as system log and will be propagated to kusto
    prefix = 'LanguageWorkerConsoleLog' if is_console_log else ''
    print(f'{prefix} {message}'.strip(),
          file=sys.stderr if is_stderr else sys.stdout,
          flush=flush_required)

    return Response(content='OK-print-logging', media_type="text/plain")


@fast_app.post("/raw_body_bytes")
async def raw_body_bytes(request: Request):
    raw_body = await request.body()
    return Response(content=raw_body, headers={'body-len': str(len(raw_body))})


@fast_app.get("/return_http_no_body")
async def return_http_no_body():
    return Response(content='', media_type="text/plain")


@fast_app.get("/return_http")
async def return_http(request: Request):
    return Response('<h1>Hello World™</h1>', media_type='text/html')


@fast_app.get("/return_http_redirect")
async def return_http_redirect(request: Request, code: str = ''):
    location = 'return_http?code={}'.format(code)
    return RedirectResponse(status_code=302,
                            url=f"http://{request.url.components[1]}/"
                                f"{location}")


@fast_app.get("/unhandled_error")
async def unhandled_error():
    1 / 0


@fast_app.get("/unhandled_urllib_error")
async def unhandled_urllib_error(img: str = ''):
    urlopen(img).read()


class UnserializableException(Exception):
    def __str__(self):
        raise RuntimeError('cannot serialize me')


@fast_app.get("/unhandled_unserializable_error")
async def unhandled_unserializable_error():
    raise UnserializableException('foo')


app = func.AsgiFunctionApp(app=fast_app,
                           http_auth_level=func.AuthLevel.ANONYMOUS)
