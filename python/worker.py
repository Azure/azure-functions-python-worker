"""Main entrypoint."""


import argparse
import os
import sys
import traceback


def parse_args():
    parser = argparse.ArgumentParser(
        description='Python Azure Functions Worker')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--workerId', dest='worker_id')
    parser.add_argument('--requestId', dest='request_id')
    return parser.parse_args()


def main():
    args = parse_args()

    # XXX: Inject a path entry so that Python import machinery
    # can find the azure.worker module.
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

    import azure.functions  # NoQA
    import azure.worker
    try:
        azure.worker.start(
            args.host, args.port, args.worker_id, args.request_id)
    except Exception:
        print(traceback.format_exc(), flush=True)
        raise


if __name__ == '__main__':
    main()
