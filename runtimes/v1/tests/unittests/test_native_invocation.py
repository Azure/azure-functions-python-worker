# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from types import SimpleNamespace

from azure_functions_runtime_v1 import native_invocation


def test_prepare_context_preserves_retry_context():
    function_info = SimpleNamespace(
        name="retry_function",
        directory="/functions/retry_function",
        requires_context=True,
        output_types={})
    args = {}
    retry_exception = SimpleNamespace(message="previous attempt failed")

    context = native_invocation._prepare_context(
        function_info, "invocation-id", args,
        retry_count=2, max_retry_count=3,
        retry_exception=retry_exception)

    assert args["context"] is context
    assert context.retry_context.retry_count == 2
    assert context.retry_context.max_retry_count == 3
    assert context.retry_context.rpc_exception is retry_exception