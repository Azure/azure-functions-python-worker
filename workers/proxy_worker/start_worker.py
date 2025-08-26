# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Main entrypoint."""

import argparse
import traceback
import asyncio

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
                        dest='grpc_max_msg_len')
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
    return parser.parse_args()


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
        'Host Address: %s:%s, Event Loop: %s',
        args.worker_id, args.request_id,
        args.host, args.port, type(asyncio.get_event_loop())
    )

    try:
        return asyncio.run(start_async(
            args.host, args.port, args.worker_id, args.request_id))
    except Exception as ex:
        error_logger.exception(
            'unhandled error in functions worker: {0}'.format(
                ''.join(traceback.format_exception(ex))))
        raise


async def start_async(host, port, worker_id, request_id):
    from . import dispatcher

    disp = await dispatcher.Dispatcher.connect(host=host, port=port,
                                               worker_id=worker_id,
                                               request_id=request_id,
                                               connect_timeout=_GRPC_CONNECTION_TIMEOUT)
    await disp.dispatch_forever()


if __name__ == '__main__':
    start()
