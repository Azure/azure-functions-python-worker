# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from datetime import timedelta

import pytest

import protos_adapter as protos


def test_enum_wrappers_match_protobuf_lookup_behavior():
    assert protos.StatusResult.Status.Value("Success") == 1
    assert protos.StatusResult.Status.Name(2) == "Cancelled"
    assert protos.BindingInfo.Direction.Value("in") == protos.BindingInfo.in_
    assert protos.RpcLog.Level.Value("None") == 6
    assert protos.RpcLog.RpcLogCategory.System == 1

    with pytest.raises(KeyError):
        protos.StatusResult.Status.Value("Missing")
    with pytest.raises(ValueError):
        protos.StatusResult.Status.Name(99)


def test_status_exception_metadata_and_binding_serialize_with_proto_defaults():
    exception = protos.RpcException(
        message="failed", stack_trace="stack", source="worker",
        type="ValueError")
    result = protos.StatusResult(
        status=protos.StatusResult.Failure, exception=exception,
        result="ignored", logs=["ignored"])
    metadata = protos.WorkerMetadata(
        runtime_name="python", runtime_version="3.15.0",
        worker_version="4.0.0", worker_bitness="64",
        custom_properties={"feature": "enabled"})
    binding = protos.BindingInfo(
        type="httpTrigger", data_type=None, direction=None)

    assert result.to_dict() == {
        "status": 0,
        "exception": {
            "message": "failed",
            "stack_trace": "stack",
            "source": "worker",
            "type": "ValueError",
        },
    }
    assert protos.StatusResult().to_dict() == {
        "status": 0, "exception": None}
    assert metadata.to_dict() == {
        "runtime_name": "python",
        "runtime_version": "3.15.0",
        "worker_version": "4.0.0",
        "worker_bitness": "64",
        "custom_properties": {"feature": "enabled"},
    }
    assert binding.to_dict() == {
        "type": "httpTrigger", "data_type": 0, "direction": 0}


def test_retry_and_function_metadata_serialize_nested_values():
    retry = protos.RpcRetryOptions(
        max_retry_count=5,
        retry_strategy="fixed_delay",
        delay_interval=timedelta(seconds=10),
        minimum_interval=2,
        maximum_interval=None,
    )
    function = protos.RpcFunctionMetadata(
        name="hello", function_id="fid", managed_dependency_enabled=True,
        directory="/app", script_file="function_app.py", entry_point="main",
        is_proxy=True, language="python",
        bindings={"req": protos.BindingInfo(
            type="httpTrigger", data_type=1, direction=0)},
        raw_bindings=["raw"], retry_options=retry,
        properties={"key": "value"},
    )

    assert retry.to_dict() == {
        "max_retry_count": 5,
        "retry_strategy": protos.RpcRetryOptions.fixed_delay,
        "delay_interval_seconds": 10,
        "minimum_interval_seconds": 2,
        "maximum_interval_seconds": None,
    }
    assert function.to_dict() == {
        "name": "hello",
        "function_id": "fid",
        "managed_dependency_enabled": True,
        "directory": "/app",
        "script_file": "function_app.py",
        "entry_point": "main",
        "is_proxy": True,
        "language": "python",
        "bindings": {
            "req": {"type": "httpTrigger", "data_type": 1,
                    "direction": 0}},
        "raw_bindings": ["raw"],
        "retry_options": retry.to_dict(),
        "properties": {"key": "value"},
    }
    assert protos.RpcRetryOptions(retry_strategy=None).retry_strategy == 0


def test_control_responses_serialize_nested_messages_and_defaults():
    result = protos.StatusResult(status=protos.StatusResult.Success)
    metadata = protos.WorkerMetadata(runtime_name="python")
    function = protos.RpcFunctionMetadata(name="hello")

    assert protos.WorkerInitResponse(
        capabilities={"A": "true"}, worker_metadata=metadata,
        result=result).to_dict() == {
            "capabilities": {"A": "true"},
            "worker_metadata": metadata.to_dict(),
            "result": result.to_dict(),
    }
    assert protos.FunctionMetadataResponse(
        use_default_metadata_indexing=True,
        function_metadata_results=[function], result=result).to_dict() == {
            "use_default_metadata_indexing": True,
            "function_metadata_results": [function.to_dict()],
            "result": result.to_dict(),
    }
    assert protos.FunctionLoadResponse(
        function_id="fid", result=result).to_dict() == {
            "function_id": "fid", "result": result.to_dict()}
    assert protos.FunctionEnvironmentReloadResponse(
        capabilities={"B": "true"}, worker_metadata=metadata,
        result=result).to_dict() == {
            "capabilities": {"B": "true"},
            "worker_metadata": metadata.to_dict(),
            "result": result.to_dict(),
    }
    assert protos.WorkerInitResponse().to_dict() == {
        "capabilities": {}, "worker_metadata": None, "result": None}
    assert protos.FunctionMetadataResponse().to_dict() == {
        "use_default_metadata_indexing": False,
        "function_metadata_results": [], "result": None}
    assert protos.FunctionLoadResponse().to_dict() == {
        "function_id": "", "result": None}
    assert protos.FunctionEnvironmentReloadResponse().to_dict() == {
        "capabilities": {}, "worker_metadata": None, "result": None}
    assert protos.WorkerStatusResponse().to_dict() == {}


def test_rpc_log_and_model_binding_data_hold_runtime_fields():
    rpc_log = protos.RpcLog(
        level=protos.RpcLog.Information, message="hello", category="worker",
        log_category=protos.RpcLog.RpcLogCategory.System,
        invocation_id="inv", event_id="event", properties={"a": "b"})
    model = protos.ModelBindingData(
        version="1.0", source="CosmosDB", content_type="application/json",
        content=b"{}")

    assert (rpc_log.level, rpc_log.message, rpc_log.category) == (
        2, "hello", "worker")
    assert (rpc_log.log_category, rpc_log.invocation_id, rpc_log.event_id) == (
        1, "inv", "event")
    assert rpc_log.properties == {"a": "b"}
    assert (model.version, model.source, model.content_type, model.content) == (
        "1.0", "CosmosDB", "application/json", b"{}")


def test_nullable_cookie_and_http_values_serialize_without_protobuf():
    cookie = protos.RpcHttpCookie(
        name="session", value="abc",
        domain=protos.NullableString("example.com"),
        path=protos.NullableString("/api"),
        expires=protos.NullableTimestamp(protos.Timestamp(1234)),
        secure=protos.NullableBool(True),
        http_only=protos.NullableBool(False),
        same_site=protos.RpcHttpCookie.SameSite.Strict,
        max_age=protos.NullableDouble(30.5),
    )
    http = protos.RpcHttp(
        status_code=201, headers={"x-count": 2},
        body=protos.TypedData(string="created"), cookies=[cookie],
        enable_content_negotiation=True)

    assert cookie.to_dict() == {
        "name": "session",
        "value": "abc",
        "domain": {"value": "example.com"},
        "path": {"value": "/api"},
        "expires": {"seconds": 1234},
        "secure": {"value": True},
        "http_only": {"value": False},
        "same_site": 2,
        "max_age": {"value": 30.5},
    }
    assert http.to_dict() == {
        "status_code": "201",
        "headers": {"x-count": "2"},
        "body": ("string", "created"),
        "cookies": [cookie.to_dict()],
        "enable_content_negotiation": True,
    }
    assert protos.RpcHttpCookie().to_dict() == {
        "name": "", "value": "", "domain": None, "path": None,
        "expires": None, "secure": None, "http_only": None,
        "same_site": 0, "max_age": None}
    assert protos.RpcHttp().to_dict() == {
        "status_code": "", "headers": {}, "body": None, "cookies": [],
        "enable_content_negotiation": False}


@pytest.mark.parametrize(
    ("kind", "values", "field"),
    (
        ("collection_string", ["a", "b"], "string"),
        ("collection_bytes", [b"a", b"b"], "bytes"),
        ("collection_sint64", [-1, 2], "sint64"),
        ("collection_double", [1.5, 2.5], "double"),
    ),
)
def test_typed_data_from_tuple_builds_collection_wrappers(kind, values, field):
    data = protos.TypedData.from_tuple((kind, values))

    assert data.WhichOneof("data") == kind
    collection = getattr(data, kind)
    assert getattr(collection, field) == values
    for other in {"string", "bytes", "sint64", "double"} - {field}:
        assert getattr(collection, other) == []


def test_typed_data_from_tuple_supports_http_model_scalars_and_empty():
    http = protos.TypedData.from_tuple(("http", {
        "method": "POST", "url": "https://example.test",
        "headers": {"content-type": "text/plain"},
        "params": {"route": "value"}, "query": {"q": "search"},
        "body": ("bytes", b"payload"),
    }))
    model = protos.TypedData.from_tuple(("model_binding_data", {
        "version": "1.0", "source": "CosmosDB",
        "content_type": "application/json", "content": b"{}",
    }))
    scalar = protos.TypedData.from_tuple(("double", 2.5))
    empty = protos.TypedData.from_tuple(None)

    assert http.WhichOneof("data") == "http"
    assert http.http.method == "POST"
    assert http.http.body.to_dict() == ("bytes", b"payload")
    assert http.to_dict()[0] == "http"
    assert model.model_binding_data.source == "CosmosDB"
    assert model.model_binding_data.content == b"{}"
    assert scalar.to_dict() == ("double", 2.5)
    assert scalar.double == 2.5
    assert scalar.string is None
    assert empty.WhichOneof("data") is None
    assert empty.to_dict() is None
    with pytest.raises(AttributeError):
        _ = scalar.not_a_typed_data_field


def test_parameter_binding_and_invocation_response_serialize_outputs():
    empty_binding = protos.ParameterBinding(name="empty")
    binding = protos.ParameterBinding(
        name="output", data=protos.TypedData(json='{"ok": true}'))
    result = protos.StatusResult(status=protos.StatusResult.Success)
    response = protos.InvocationResponse(
        invocation_id="inv", return_value=protos.TypedData(string="done"),
        result=result, output_data=[binding, empty_binding])

    assert empty_binding.WhichOneof("rpc_data") is None
    assert empty_binding.to_dict() == {"name": "empty", "data": None}
    assert binding.WhichOneof("rpc_data") == "data"
    assert response.to_dict() == {
        "invocation_id": "inv",
        "return_value": ("string", "done"),
        "result": result.to_dict(),
        "output_data": [
            {"name": "output", "data": ("json", '{"ok": true}')},
            {"name": "empty", "data": None},
        ],
    }
    assert protos.InvocationResponse().to_dict() == {
        "invocation_id": "", "return_value": None, "result": None,
        "output_data": []}
