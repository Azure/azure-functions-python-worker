import logging
import sys
from urllib.request import urlopen

import azure.functions as func
from flask import Flask, request, Response, redirect, url_for

flask_app = Flask(__name__)
logger = logging.getLogger("my-function")


@flask_app.get("/debug_logging")
def debug_logging():
    logging.critical('logging critical', exc_info=True)
    logging.info('logging info', exc_info=True)
    logging.warning('logging warning', exc_info=True)
    logging.debug('logging debug', exc_info=True)
    logging.error('logging error', exc_info=True)

    return 'OK-debug'


@flask_app.get("/debug_user_logging")
def debug_user_logging():
    logger.setLevel(logging.DEBUG)

    logger.critical('logging critical', exc_info=True)
    logger.info('logging info', exc_info=True)
    logger.warning('logging warning', exc_info=True)
    logger.debug('logging debug', exc_info=True)
    logger.error('logging error', exc_info=True)
    return 'OK-user-debug'


@flask_app.get("/print_logging")
def print_logging():
    flush_required = False
    is_console_log = False
    is_stderr = False

    message = request.args.get("message", '')

    if request.args.get("flush") == 'true':
        flush_required = True
    if request.args.get("console") == 'true':
        is_console_log = True
    if request.args.get("is_stderr") == 'true':
        is_stderr = True

    # Adding LanguageWorkerConsoleLog will make function host to treat
    # this as system log and will be propagated to kusto
    prefix = 'LanguageWorkerConsoleLog' if is_console_log else ''
    print(f'{prefix} {message}'.strip(),
          file=sys.stderr if is_stderr else sys.stdout,
          flush=flush_required)

    return 'OK-print-logging'


@flask_app.post("/raw_body_bytes")
def raw_body_bytes():
    body = request.get_data()

    return Response(body, headers={'body-len': str(len(body))})


@flask_app.get("/return_http_no_body")
def return_http_no_body():
    return ''


@flask_app.get("/return_http")
def return_http():
    return Response('<h1>Hello World™</h1>', mimetype='text/html')


@flask_app.get("/return_http_redirect")
def return_http_redirect(code: str = ''):
    return redirect(url_for('return_http'))


@flask_app.get("/unhandled_error")
def unhandled_error():
    1 / 0


@flask_app.get("/unhandled_urllib_error")
def unhandled_urllib_error(img: str = ''):
    urlopen(img).read()


class UnserializableException(Exception):
    def __str__(self):
        raise RuntimeError('cannot serialize me')


@flask_app.get("/unhandled_unserializable_error")
def unhandled_unserializable_error():
    raise UnserializableException('foo')


app = func.WsgiFunctionApp(app=flask_app.wsgi_app,
                           http_auth_level=func.AuthLevel.ANONYMOUS)
