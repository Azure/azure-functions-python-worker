"""Main entrypoint."""


import argparse

from . import aio_compat
from . import dispatcher
from . import logging
from .logging import error_logger, logger


def parse_args():
    parser = argparse.ArgumentParser(
        description='Python Azure Functions Worker')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--workerId', dest='worker_id')
    parser.add_argument('--requestId', dest='request_id')
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['TRACE', 'INFO', 'WARNING', 'ERROR'],)
    parser.add_argument('--log-to', type=str, default=None,
                        help='log destination: stdout, stderr, '
                             'syslog, or a file path')
    parser.add_argument('--grpcMaxMessageLength', type=int,
                        dest='grpc_max_msg_len')
    return parser.parse_args()


def main():
    args = parse_args()
    logging.setup(log_level=args.log_level, log_destination=args.log_to)

    logger.info('Starting Azure Functions Python Worker.')
    logger.info('Worker ID: %s, Request ID: %s, Host Address: %s:%s',
                args.worker_id, args.request_id, args.host, args.port)

    try:
        return aio_compat.run(start_async(
            args.host, args.port, args.worker_id, args.request_id,
            args.grpc_max_msg_len))
    except Exception:
        error_logger.exception('unhandled error in functions worker')
        raise


async def start_async(host, port, worker_id, request_id, grpc_max_msg_len):
    disp = await dispatcher.Dispatcher.connect(
        host, port, worker_id, request_id,
        connect_timeout=5.0, max_msg_len=grpc_max_msg_len)

    await disp.dispatch_forever()
