# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import contextlib
import io
import sys
import unittest
from unittest.mock import AsyncMock, patch

from proxy_worker import start_worker


class TestParseArgs(unittest.TestCase):
    legacy_args = [
        '--host', 'legacy-host', '--port', '5001',
        '--workerId', 'legacy-worker', '--requestId', 'legacy-request',
        '--grpcMaxMessageLength', '1024',
    ]
    functions_args = [
        '--functions-uri', 'http://localhost:5002',
        '--functions-worker-id', 'new-worker',
        '--functions-request-id', 'new-request',
        '--functions-grpc-max-message-length', '2048',
    ]

    def parse(self, args):
        with patch.object(sys, 'argv', ['proxy_worker', *args]):
            return start_worker.parse_args()

    def assert_resolved(self, args, host, port, worker_id, request_id,
                        max_size):
        self.assertEqual(
            (args.host, args.port, args.worker_id, args.request_id,
             args.grpc_max_msg_len),
            (host, port, worker_id, request_id, max_size),
        )

    def assert_invalid(self, args):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                self.parse(args)
        self.assertEqual(error.exception.code, 2)

    def test_legacy_arguments_keep_explicit_max_message_length(self):
        self.assert_resolved(
            self.parse(self.legacy_args), 'legacy-host', 5001,
            'legacy-worker', 'legacy-request', 1024,
        )

    def test_functions_arguments_normalize_legacy_namespace_fields(self):
        self.assert_resolved(
            self.parse(self.functions_args), 'localhost', 5002,
            'new-worker', 'new-request', 2048,
        )

    def test_functions_arguments_win_regardless_of_command_line_order(self):
        for args in (self.legacy_args + self.functions_args,
                     self.functions_args + self.legacy_args):
            with self.subTest(args=args):
                self.assert_resolved(
                    self.parse(args), 'localhost', 5002,
                    'new-worker', 'new-request', 2048,
                )

    def test_legacy_values_fill_only_missing_functions_values(self):
        overrides = [
            (['--functions-uri', 'http://localhost:5002'],
             ('localhost', 5002, 'legacy-worker', 'legacy-request', 1024)),
            (['--functions-worker-id', 'new-worker'],
             ('legacy-host', 5001, 'new-worker', 'legacy-request', 1024)),
            (['--functions-request-id', 'new-request'],
             ('legacy-host', 5001, 'legacy-worker', 'new-request', 1024)),
            (['--functions-grpc-max-message-length', '2048'],
             ('legacy-host', 5001, 'legacy-worker', 'legacy-request', 2048)),
        ]
        for flags, expected in overrides:
            with self.subTest(flags=flags):
                self.assert_resolved(
                    self.parse(self.legacy_args + flags), *expected,
                )

    def test_missing_max_message_length_defaults_to_unlimited(self):
        for args in (self.legacy_args[:-2], self.functions_args[:-2]):
            with self.subTest(args=args):
                self.assertEqual(self.parse(args).grpc_max_msg_len, -1)

    def test_explicit_unlimited_message_length_is_accepted(self):
        for flag in ('--grpcMaxMessageLength',
                     '--functions-grpc-max-message-length'):
            with self.subTest(flag=flag):
                args = self.parse(self.legacy_args[:-2] + [flag, '-1'])
                self.assertEqual(args.grpc_max_msg_len, -1)

    def test_uri_accepts_root_slash_and_ipv6(self):
        for uri, host, port in (
            ('http://localhost:1/', 'localhost', 1),
            ('http://127.0.0.1:65535', '127.0.0.1', 65535),
            ('http://[::1]:5002/', '::1', 5002),
        ):
            with self.subTest(uri=uri):
                args = self.parse(
                    self.legacy_args + ['--functions-uri', uri],
                )
                self.assertEqual((args.host, args.port), (host, port))

    def test_invalid_uri_never_falls_back_to_legacy_host_and_port(self):
        for uri in (
            '', 'localhost:5002', 'https://localhost:5002',
            'http://:5002', 'http://localhost', 'http://localhost:bad',
            'http://localhost:65536',
            'http://user@localhost:5002',
            'http://localhost:5002/path', 'http://localhost:5002?query=yes',
            'http://localhost:5002#fragment', 'http://[::1:5002',
        ):
            with self.subTest(uri=uri):
                self.assert_invalid(
                    self.legacy_args + ['--functions-uri', uri],
                )


class TestStart(unittest.TestCase):
    def test_start_passes_resolved_arguments_including_message_length(self):
        cases = (
            (TestParseArgs.legacy_args,
             ('legacy-host', 5001, 'legacy-worker', 'legacy-request', 1024)),
            (TestParseArgs.functions_args,
             ('localhost', 5002, 'new-worker', 'new-request', 2048)),
            (TestParseArgs.functions_args[:-2],
             ('localhost', 5002, 'new-worker', 'new-request', -1)),
        )
        for flags, expected in cases:
            with self.subTest(flags=flags), \
                    patch.object(sys, 'argv', ['proxy_worker', *flags]), \
                    patch('proxy_worker.utils.dependency.DependencyManager.'
                          'initialize'), \
                    patch('proxy_worker.utils.dependency.DependencyManager.'
                          'use_worker_dependencies'), \
                    patch('proxy_worker.logging.setup'), \
                    patch.object(start_worker, 'start_async',
                                 autospec=True) as start_async:
                start_worker.start()
                start_async.assert_awaited_once_with(*expected)


class TestStartAsync(unittest.IsolatedAsyncioTestCase):
    async def test_start_async_propagates_message_length_and_dispatches(self):
        for max_size in (None, 4096):
            with self.subTest(max_size=max_size), \
                    patch('proxy_worker.dispatcher.Dispatcher.connect',
                          new_callable=AsyncMock) as connect:
                dispatcher = connect.return_value
                dispatcher.dispatch_forever = AsyncMock()
                kwargs = {} if max_size is None else {
                    'grpc_max_msg_len': max_size,
                }
                await start_worker.start_async(
                    '::1', 5002, 'worker', 'request', **kwargs,
                )
                connect.assert_awaited_once_with(
                    host='::1', port=5002, worker_id='worker',
                    request_id='request',
                    connect_timeout=start_worker._GRPC_CONNECTION_TIMEOUT,
                    grpc_max_msg_len=-1 if max_size is None else max_size,
                )
                dispatcher.dispatch_forever.assert_awaited_once_with()
