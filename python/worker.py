"""Main entrypoint."""


try:
    from azure.functions_worker.main import main

except ImportError:
    # Compatibility with hard-bundled pre-beta worker versions in
    # deployed function apps.
    import argparse
    import traceback

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

        import azure.functions  # NoQA
        import azure.functions_worker
        from azure.functions_worker import aio_compat

        try:
            return aio_compat.run(azure.functions_worker.start_async(
                args.host, args.port, args.worker_id, args.request_id,
                args.grpc_max_msg_len))
        except Exception:
            print(traceback.format_exc(), flush=True)
            raise


if __name__ == '__main__':
    main()
