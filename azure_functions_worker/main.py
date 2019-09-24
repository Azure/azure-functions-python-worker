"""Main entrypoint."""


import argparse
import sys
import os
from pathlib import Path

from . import aio_compat
from . import dispatcher
from . import logging
from . import constants
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


def setup_user_pkg_paths():
    minor_version = sys.version_info[1]

    home = Path.home()
    pkgs_path = os.path.join(home, constants.PKGS_PATH)
    venv_pkgs_path = os.path.join(home, constants.VENV_PKGS_PATH)

    if minor_version == 6:
        sys.path.insert(1, os.path.join(venv_pkgs_path, constants.PKGS_36))
        sys.path.insert(1, os.path.join(pkgs_path, constants.PKGS_36))
    elif minor_version == 7:
        sys.path.insert(1, os.path.join(venv_pkgs_path, constants.PKGS_37))
        sys.path.insert(1, os.path.join(pkgs_path, constants.PKGS_37))
    else:
        raise RuntimeError(f'Unsupported Python version: 3.{minor_version}')

    logger.info(f'Added user package paths for Python 3.{minor_version}')


def main():
    args = parse_args()
    setup_user_pkg_paths()
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

    disp.load_bindings()

    await disp.dispatch_forever()
