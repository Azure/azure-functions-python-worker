# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
from unittest.mock import patch

from tests.utils import testutils

REQUEST_TIMEOUT_SEC = 5


class TestValidSnakeCaseFunctions(testutils.WebHostTestCase):
    def setUp(self):
        self._patch_environ = patch.dict('os.environ', os.environ.copy())
        self._patch_environ.start()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'snake_case_functions'

    @testutils.retryable_test(3, 5)
    def test_classic_snake_case(self):
        r = self.webhost.request('GET', 'classic_snake_case',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_single_underscore(self):
        r = self.webhost.request('GET', 'single_underscore',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_underscore_prefix(self):
        r = self.webhost.request('GET', 'underscore_prefix',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_underscore_suffix(self):
        r = self.webhost.request('GET', 'underscore_suffix',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_ultimate_combo(self):
        r = self.webhost.request('GET', 'ultimate_combo',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_underscore_prefix_snake(self):
        r = self.webhost.request('GET', 'underscore_prefix_snake',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_underscore_suffix_snake(self):
        r = self.webhost.request('GET', 'underscore_suffix_snake',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_double_underscore(self):
        r = self.webhost.request('GET', 'double_underscore',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_double_underscore_prefix(self):
        r = self.webhost.request('GET', 'double_underscore_prefix',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_double_underscore_suffix(self):
        r = self.webhost.request('GET', 'double_underscore_suffix',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_just_double_underscore(self):
        r = self.webhost.request('GET', 'just_double_underscore',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_python_main_keyword(self):
        r = self.webhost.request('GET', 'python_main_keyword',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )

    @testutils.retryable_test(3, 5)
    def test_ultimate_combo2(self):
        r = self.webhost.request('GET', 'ultimate_combo2',
                                 params={'name': 'query'},
                                 timeout=REQUEST_TIMEOUT_SEC)
        self.assertTrue(r.ok)
        self.assertEqual(
            r.content,
            b'Hello, query.'
        )
