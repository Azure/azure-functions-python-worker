# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest

from azure_functions_fastapi.http_v2 import http_coordinator


@pytest.fixture(autouse=True)
def clear_http_contexts():
    http_coordinator._context_references.clear()
    yield
    http_coordinator._context_references.clear()


@pytest.mark.asyncio
async def test_response_consumption_removes_invocation_context():
    invocation_id = "test-invocation"
    request = object()
    response = object()

    http_coordinator.set_http_request(invocation_id, request)
    assert await http_coordinator.get_http_request_async(invocation_id) \
        is request

    http_coordinator.set_http_response(invocation_id, response)

    assert await http_coordinator.await_http_response_async(invocation_id) \
        is response
    assert invocation_id not in http_coordinator._context_references
