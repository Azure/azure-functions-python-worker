# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from azure_functions_runtime import handle_event, host_configuration
from tests import protos


@pytest.fixture(autouse=True)
def init_state(monkeypatch, tmp_path):
    with host_configuration.reset_host_configuration():
        pass
    monkeypatch.setenv("AzureWebJobsScriptRoot", str(tmp_path))
    monkeypatch.setattr(handle_event, "is_envvar_true", lambda _: False)
    monkeypatch.setattr(handle_event, "load_binding_registry", lambda: None)
    monkeypatch.setattr(handle_event, "load_function_metadata",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(handle_event.HttpV2Registry, "http_v2_enabled",
                        lambda: False)
    monkeypatch.setattr(handle_event.otel_manager,
                        "get_azure_monitor_available", lambda: False)
    monkeypatch.setattr(handle_event.otel_manager,
                        "get_otel_libs_available", lambda: False)
    yield
    with host_configuration.reset_host_configuration():
        pass


def request(capabilities=None):
    return SimpleNamespace(
        request=protos.StreamingMessage(
            worker_init_request=protos.WorkerInitRequest(
                capabilities=capabilities or {},
                function_app_directory="host-supplied-not-worker-local")),
        properties={"protos": protos, "host": "127.0.0.1"})


@pytest.mark.asyncio
@pytest.mark.parametrize("source,status,expected", [
    (b'{"version":"2.0"}', protos.HostConfiguration.Available, b'{"version":"2.0"}'),
    (b'/*c*/ { "a": [1,], }', protos.HostConfiguration.Available, b'{"a":[1]}'),
    (b"", protos.HostConfiguration.Error, b""),
    (b"\xff\xfe", protos.HostConfiguration.Error, b""),
    (b"[]", protos.HostConfiguration.Error, b""),
    (b'"string"', protos.HostConfiguration.Error, b""),
    (b"1E+2", protos.HostConfiguration.Error, b""),
    (b"null", protos.HostConfiguration.Error, b""),
    (b"true", protos.HostConfiguration.Error, b""),
    (b"false", protos.HostConfiguration.Error, b""),
    (b"/* leading */ []", protos.HostConfiguration.Error, b""),
    (b"{invalid-json", protos.HostConfiguration.Error, b""),
    (None, protos.HostConfiguration.Missing, b""),
    (b"\xff", protos.HostConfiguration.Error, b""),
    (b"x" * 65537, protos.HostConfiguration.TooLarge, b""),
], ids=("available", "jsonc", "empty", "bom-only", "array", "string", "number",
        "null", "true", "false", "comment-array", "malformed-json", "missing",
        "error", "too-large"))
async def test_delivery_preserves_init_and_wire_presence(
        tmp_path, source, status, expected):
    if source is not None:
        (tmp_path / "host.json").write_bytes(source)
    baseline = await handle_event.worker_init_request(request())
    assert not baseline.HasField("host_configuration")
    assert host_configuration._snapshot is None
    result = await handle_event.worker_init_request(
        request({"HostConfiguration": "1"}))
    assert result.result.status == protos.StatusResult.Success
    assert result.capabilities == baseline.capabilities
    assert result.worker_metadata == baseline.worker_metadata
    assert result.DESCRIPTOR.fields_by_name["host_configuration"].number == 6
    decoded = protos.WorkerInitResponse.FromString(result.SerializeToString())
    assert decoded.HasField("host_configuration")
    assert decoded.host_configuration.status == status
    assert decoded.host_configuration.content == expected
    (tmp_path / "host.json").write_bytes(b"changed")
    result.host_configuration.content = b"response mutation"
    repeated = await handle_event.worker_init_request(
        request({"HostConfiguration": "1"}))
    assert repeated.host_configuration == decoded.host_configuration


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["indexing", "http"])
async def test_genuine_initialization_failures_keep_delivery(
        monkeypatch, tmp_path, failure):
    (tmp_path / "host.json").write_bytes(b"{}")
    if failure == "indexing":
        target = "load_function_metadata"
        error = RuntimeError("indexing failed")
    else:
        target = "initialize_http_server"
        error = handle_event.HttpServerInitError("streaming failed")
        monkeypatch.setattr(handle_event.HttpV2Registry, "http_v2_enabled",
                            lambda: True)
    with patch.object(handle_event, target, side_effect=error):
        response = await handle_event.worker_init_request(
            request({"HostConfiguration": "1"}))
    assert response.result.status == protos.StatusResult.Failure
    assert response.host_configuration.status == protos.HostConfiguration.Available
    assert response.host_configuration.content == b"{}"


@pytest.mark.asyncio
async def test_specialization_starts_new_snapshot_generation(tmp_path):
    (tmp_path / "host.json").write_bytes(b'{"value":"old"}')
    await handle_event.worker_init_request(request({"HostConfiguration": "1"}))
    next_app = tmp_path / "next"
    next_app.mkdir()
    (next_app / "host.json").write_bytes(b'{"value":"new"}')
    reload_request = SimpleNamespace(
        request=protos.StreamingMessage(
            function_environment_reload_request=(
                protos.FunctionEnvironmentReloadRequest(environment_variables={
                    "AzureWebJobsScriptRoot": str(next_app)}))),
        properties={"protos": protos, "host": "127.0.0.1"})
    with patch.dict(os.environ), \
            patch.object(handle_event.time, "tzset", create=True):
        response = await handle_event.function_environment_reload_request(
            reload_request)
        assert response.result.status == protos.StatusResult.Success
        assert host_configuration._snapshot is None
        response = await handle_event.worker_init_request(
            request({"HostConfiguration": "1"}))
        assert response.host_configuration.content == b'{"value":"new"}'
