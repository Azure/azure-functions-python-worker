"""Main entrypoint."""


import argparse
import traceback


def parse_args():
    parser = argparse.ArgumentParser(
        description='Python Azure Functions Worker')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    parser.add_argument('--workerId', dest='worker_id')
    parser.add_argument('--requestId', dest='request_id')
    parser.add_argument('--grpcMaxMessageLength', type=int,
                        dest='grpc_max_msg_len')
    return parser.parse_args()


def main():
    args = parse_args()

    import azure.functions  # NoQA
    import azure.functions_worker

    try:
        azure.functions_worker.start(
            args.host, args.port, args.worker_id, args.request_id,
            args.grpc_max_msg_len)
    except Exception:
        print(traceback.format_exc(), flush=True)
        raise


if __name__ == '__main__':
    main()
