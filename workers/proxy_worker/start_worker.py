# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Main entrypoint."""

import argparse
import traceback
import asyncio
from urllib.parse import urlsplit

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:
    pass

_GRPC_CONNECTION_TIMEOUT = 5.0


def parse_args():
    parser = argparse.ArgumentParser(
        description='Python Azure Functions Worker')
    parser.add_argument('--host',
                        help="host address")
    parser.add_argument('--port', type=int,
                        help='port number')
    parser.add_argument('--workerId', dest='worker_id',
                        help='id for the worker')
    parser.add_argument('--requestId', dest='request_id',
                        help='id of the request')
    parser.add_argument('--grpcMaxMessageLength', type=int,
                        dest='grpc_max_msg_len', default=-1)
    parser.add_argument('--functions-uri', dest='functions_uri', type=str,
                        help='URI with IP Address and Port used to'
                             ' connect to the Host via gRPC.')
    parser.add_argument('--functions-worker-id',
                        dest='functions_worker_id', type=str,
                        help='Worker ID assigned to this language worker.')
    parser.add_argument('--functions-request-id', dest='functions_request_id',
                        type=str, help='Request ID used for gRPC communication '
                                       'with the Host.')
    parser.add_argument('--functions-grpc-max-message-length', type=int,
                        dest='functions_grpc_max_msg_len',
                        help='Max grpc_local message length for Functions')
    args = parser.parse_args()

    if args.functions_uri is not None:
        try:
            uri = urlsplit(args.functions_uri)
            host, port = uri.hostname, uri.port
            if (uri.scheme != 'http' or not host or port is None
                    or uri.username is not None or uri.password is not None
                    or uri.path not in ('', '/') or uri.query or uri.fragment):
                raise ValueError
        except ValueError:
            parser.error('--functions-uri must be an http URI with a hostname '
                         'and explicit port, without credentials, path, query '
                         'or fragment')
        args.host, args.port = host, port

    for field in ('worker_id', 'request_id', 'grpc_max_msg_len'):
        value = getattr(args, f'functions_{field}')
        if value is not None:
            setattr(args, field, value)

    return args


def start():
    from .utils.dependency import DependencyManager
    DependencyManager.initialize()
    DependencyManager.use_worker_dependencies()

    from . import logging
    from .logging import error_logger, logger

    args = parse_args()
    logging.setup(log_level="INFO", log_destination=None)

    logger.info("Args: %s", args)
    logger.info(
        'Starting proxy worker. Worker ID: %s, Request ID: %s, '
        'Host Address: %s:%s',
        args.worker_id, args.request_id,
        args.host, args.port)

    try:
        return asyncio.run(start_async(
            args.host, args.port, args.worker_id, args.request_id,
            args.grpc_max_msg_len))
    except Exception as ex:
        error_logger.exception(
            'unhandled error in functions worker: {0}'.format(
                ''.join(traceback.format_exception(ex))))
        raise


async def start_async(host, port, worker_id, request_id, grpc_max_msg_len=-1):
    from . import dispatcher

    disp = await dispatcher.Dispatcher.connect(
        host=host, port=port, worker_id=worker_id, request_id=request_id,
        connect_timeout=_GRPC_CONNECTION_TIMEOUT,
        grpc_max_msg_len=grpc_max_msg_len)
    await disp.dispatch_forever()


if __name__ == '__main__':
    start()
