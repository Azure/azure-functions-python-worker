import unittest

from azure_functions_worker.main import create_args_parser


class TestMain(unittest.TestCase):

    def test_args_parser(self):
        parser = create_args_parser()
        parsed = parser.parse_args(
            ['--host', '127.0.0.1',
             '--port', '50821',
             '--workerId', 'e9efd817-47a1-45dc-9e20-e6f975d7a025',
             '--requestId', 'cbef5957-cdb3-4462-9ee7-ac9f91be0a51',
             '--grpcMaxMessageLength', '2147483647',
             '--functions-uri', 'http://127.0.0.1:50821',
             '--functions-worker-id', 'e9efd817-47a1-45dc-9e20-e6f975d7a025',
             '--functions-request-id', 'cbef5957-cdb3-4462-9ee7-ac9f91be0a51',
             '--functions-grpc-max-message-length', '2147483647'])
        self.assertEqual(parsed.host, '127.0.0.1')
        self.assertEqual(parsed.worker_id,
                         'e9efd817-47a1-45dc-9e20-e6f975d7a025')
        self.assertEqual(parsed.request_id,
                         'cbef5957-cdb3-4462-9ee7-ac9f91be0a51')
        self.assertEqual(parsed.grpc_max_msg_len, 2147483647)
        self.assertEqual(parsed.functions_uri, 'http://127.0.0.1:50821')
        self.assertEqual(parsed.functions_worker_id,
                         'e9efd817-47a1-45dc-9e20-e6f975d7a025')
        self.assertEqual(parsed.functions_request_id,
                         'cbef5957-cdb3-4462-9ee7-ac9f91be0a51')
        self.assertEqual(parsed.functions_grpc_max_msg_len, 2147483647)
