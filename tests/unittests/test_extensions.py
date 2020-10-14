# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from unittest import TestCase, mock

from azure_functions_worker import extensions


class TestExtensions(TestCase):

    def tearDown(self):
        extensions._EXTENSIONS_CONTEXT.clear()

    def test_register_before_invocation_request(self):
        mock_cb = mock.Mock()
        mock_cb2 = mock.Mock()
        extensions.register_before_invocation_request(mock_cb)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["BEFORE_INVOCATION_REQUEST_CALLBACKS"][0],
            mock_cb,
        )
        extensions.register_before_invocation_request(mock_cb2)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["BEFORE_INVOCATION_REQUEST_CALLBACKS"][1],
            mock_cb2,
        )

    def test_register_after_invocation_request(self):
        mock_cb = mock.Mock()
        mock_cb2 = mock.Mock()
        extensions.register_after_invocation_request(mock_cb)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["AFTER_INVOCATION_REQUEST_CALLBACKS"][0],
            mock_cb,
        )
        extensions.register_after_invocation_request(mock_cb2)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["AFTER_INVOCATION_REQUEST_CALLBACKS"][1],
            mock_cb2,
        )

    def test_clear_before_invocation_request_callbacks(self):
        mock_cb = mock.Mock()
        extensions.register_before_invocation_request(mock_cb)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["BEFORE_INVOCATION_REQUEST_CALLBACKS"][0],
            mock_cb,
        )
        extensions.clear_before_invocation_request_callbacks()
        self.assertIsNone(
            extensions._EXTENSIONS_CONTEXT. \
            get("BEFORE_INVOCATION_REQUEST_CALLBACKS"),
        )

    def test_clear_after_invocation_request_callbacks(self):
        mock_cb = mock.Mock()
        extensions.register_after_invocation_request(mock_cb)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["AFTER_INVOCATION_REQUEST_CALLBACKS"][0],
            mock_cb,
        )
        extensions.clear_after_invocation_request_callbacks()
        self.assertIsNone(
            extensions._EXTENSIONS_CONTEXT. \
            get("AFTER_INVOCATION_REQUEST_CALLBACKS"),
        )

    def test_get_before_invocation_request_callbacks(self):
        mock_cb = mock.Mock()
        extensions.register_before_invocation_request(mock_cb)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["BEFORE_INVOCATION_REQUEST_CALLBACKS"][0],
            mock_cb,
        )
        self.assertEqual(
            extensions.get_before_invocation_request_callbacks()[0],
            mock_cb
        )

    def test_get_after_invocation_request_callbacks(self):
        mock_cb = mock.Mock()
        extensions.register_after_invocation_request(mock_cb)
        self.assertEqual(
            extensions._EXTENSIONS_CONTEXT \
            ["AFTER_INVOCATION_REQUEST_CALLBACKS"][0],
            mock_cb,
        )
        self.assertEqual(
            extensions.get_after_invocation_request_callbacks()[0],
            mock_cb
        )
