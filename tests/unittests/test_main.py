import sys
import unittest
from unittest.mock import patch

from azure_functions_worker.main import parse_args


class TestMain(unittest.TestCase):

    @patch.object(
        sys,
        "argv",
        [
            "xxx",
            "--host",
            "127.0.0.1",
            "--port",
            "50821",
            "--workerId",
            "e9efd817-47a1-45dc-9e20-e6f975d7a025",
            "--requestId",
            "cbef5957-cdb3-4462-9ee7-ac9f91be0a51",
            "--grpcMaxMessageLength",
            "2147483647",
            "--functions-uri",
            "http://127.0.0.1:50821",
            "--functions-worker-id",
            "e9efd817-47a1-45dc-9e20-e6f975d7a025",
            "--functions-request-id",
            "cbef5957-cdb3-4462-9ee7-ac9f91be0a51",
            "--functions-grpc-max-message-length",
            "2147483647",
        ],
    )
    def test_all_args(self):
        args = parse_args()
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 50821)
        self.assertEqual(args.worker_id, "e9efd817-47a1-45dc-9e20-e6f975d7a025")
        self.assertEqual(args.request_id, "cbef5957-cdb3-4462-9ee7-ac9f91be0a51")
        self.assertEqual(args.grpc_max_msg_len, 2147483647)
        self.assertEqual(args.functions_uri, "http://127.0.0.1:50821")
        self.assertEqual(
            args.functions_worker_id, "e9efd817-47a1-45dc-9e20-e6f975d7a025"
        )
        self.assertEqual(
            args.functions_request_id, "cbef5957-cdb3-4462-9ee7-ac9f91be0a51"
        )
        self.assertEqual(args.functions_grpc_max_msg_len, 2147483647)

    @patch.object(
        sys,
        "argv",
        [
            "xxx",
            "--host",
            "127.0.0.1",
            "--port",
            "50821",
            "--workerId",
            "e9efd817-47a1-45dc-9e20-e6f975d7a025",
            "--requestId",
            "cbef5957-cdb3-4462-9ee7-ac9f91be0a51",
            "--grpcMaxMessageLength",
            "2147483647",
        ],
    )
    def test_old_args(self):
        args = parse_args()
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 50821)
        self.assertEqual(args.worker_id, "e9efd817-47a1-45dc-9e20-e6f975d7a025")
        self.assertEqual(args.request_id, "cbef5957-cdb3-4462-9ee7-ac9f91be0a51")
        self.assertEqual(args.grpc_max_msg_len, 2147483647)
        self.assertIsNone(args.functions_uri)
        self.assertIsNone(args.functions_worker_id)
        self.assertIsNone(args.functions_request_id)
        self.assertIsNone(args.functions_grpc_max_msg_len)

    @patch.object(
        sys,
        "argv",
        [
            "xxx",
            "--functions-uri",
            "http://127.0.0.1:50821",
            "--functions-worker-id",
            "e9efd817-47a1-45dc-9e20-e6f975d7a025",
            "--functions-request-id",
            "cbef5957-cdb3-4462-9ee7-ac9f91be0a51",
            "--functions-grpc-max-message-length",
            "2147483647",
        ],
    )
    def test_new_args(self):
        args = parse_args()
        self.assertEqual(args.functions_uri, "http://127.0.0.1:50821")
        self.assertEqual(
            args.functions_worker_id, "e9efd817-47a1-45dc-9e20-e6f975d7a025"
        )
        self.assertEqual(
            args.functions_request_id, "cbef5957-cdb3-4462-9ee7-ac9f91be0a51"
        )
        self.assertEqual(args.functions_grpc_max_msg_len, 2147483647)

    @patch.object(
        sys,
        "argv",
        [
            "xxx",
            "--host",
            "dummy_host",
            "--port",
            "12345",
            "--invalid-arg",
            "invalid_value",
        ],
    )
    def test_invalid_args(self):
        with self.assertRaises(SystemExit) as context:
            parse_args()
        self.assertEqual(context.exception.code, 2)
