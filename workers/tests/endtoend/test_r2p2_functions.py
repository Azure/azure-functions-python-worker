# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
from unittest import skipUnless
from urllib.parse import parse_qs, urlparse

from tests.utils import testutils


REQUEST_TIMEOUT_SEC = 5
R2P2_NATIVE_MARKER = (
    'NATIVE-INVOKE-PATH active (prost in Rust, no Python protobuf on '
    'the invocation hot path)'
)


def _assert_http_round_trip(test_case, response, *, runtime, status_code):
    test_case.assertEqual(response.status_code, status_code)
    test_case.assertEqual(response.headers['x-r2p2-runtime'], runtime)
    payload = response.json()
    url = payload.pop('url')
    test_case.assertEqual(payload, {
        'body': f'{runtime}-body',
        'header': f'{runtime}-header',
        'method': 'POST',
        'query': f'{runtime}-query',
    })
    parsed_url = urlparse(url)
    test_case.assertEqual(
        parsed_url.path,
        f'/api/r2p2_{runtime.split("-")[0]}_response',
    )
    query_params = parse_qs(parsed_url.query)
    test_case.assertEqual(
        query_params.get('query'),
        [f'{runtime}-query'],
    )

    cookie_headers = response.raw.headers.getlist('Set-Cookie')
    test_case.assertEqual(len(cookie_headers), 2)
    normalized = [header.lower() for header in cookie_headers]
    prefix = runtime.split('-')[0]
    test_case.assertTrue(any(
        f'r2p2_{prefix}_session=active' in header
        and 'httponly' in header
        and 'samesite=strict' in header
        and 'max-age=120' in header
        for header in normalized
    ))
    test_case.assertTrue(any(
        f'r2p2_{prefix}_theme=dark' in header
        and 'samesite=lax' in header
        for header in normalized
    ))


@skipUnless(sys.version_info[:2] >= (3, 15),
            'R2P2 integration requires Python 3.15+.')
class TestR2P2V1RuntimeIntegration(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions'

    @testutils.retryable_test(3, 5)
    def test_sync_and_async_native_http_round_trip(self):
        sync_response = self.webhost.request(
            'GET',
            'default_template',
            params={'name': 'r2p2-v1-sync'},
            timeout=REQUEST_TIMEOUT_SEC,
        )
        self.assertEqual(sync_response.status_code, 200)
        self.assertEqual(
            sync_response.text,
            'Hello, r2p2-v1-sync. This HTTP triggered function executed '
            'successfully.',
        )

        response = self.webhost.request(
            'POST',
            'r2p2_v1_response',
            params={'query': 'v1-async-query'},
            headers={'x-r2p2-input': 'v1-async-header'},
            data=b'v1-async-body',
            timeout=REQUEST_TIMEOUT_SEC,
        )

        _assert_http_round_trip(
            self, response, runtime='v1-async', status_code=202)
        self.assertTrue(
            self.wait_for_host_log(R2P2_NATIVE_MARKER),
            'The v1 invocation did not use the R2P2 native path.',
        )


@skipUnless(sys.version_info[:2] >= (3, 15),
            'R2P2 integration requires Python 3.15+.')
class TestR2P2V2RuntimeIntegration(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER.joinpath(
            'http_functions', 'r2p2_v2')

    @testutils.retryable_test(3, 5)
    def test_sync_and_async_native_http_round_trip(self):
        response = self.webhost.request(
            'POST',
            'r2p2_v2_response',
            params={'query': 'v2-sync-query'},
            headers={'x-r2p2-input': 'v2-sync-header'},
            data=b'v2-sync-body',
            timeout=REQUEST_TIMEOUT_SEC,
        )

        _assert_http_round_trip(
            self, response, runtime='v2-sync', status_code=203)
        async_response = self.webhost.request(
            'GET',
            'r2p2_v2_async',
            timeout=REQUEST_TIMEOUT_SEC,
        )
        self.assertEqual(async_response.status_code, 200)
        self.assertEqual(async_response.text, 'v2-async')
        self.assertEqual(
            async_response.headers['x-r2p2-runtime'], 'v2-async')
        self.assertTrue(
            self.wait_for_host_log(R2P2_NATIVE_MARKER),
            'The v2 invocation did not use the R2P2 native path.',
        )
