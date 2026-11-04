# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from unittest.mock import Mock, patch

import pytest

from azure_functions_worker import dispatcher, host_configuration, protos


@pytest.fixture
def worker(monkeypatch, tmp_path):
    with host_configuration.reset_host_configuration():
        pass
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(dispatcher, "is_envvar_true", lambda _: False)
    monkeypatch.setattr(dispatcher, "check_python_eol", lambda: None)
    monkeypatch.setattr(dispatcher.bindings, "load_binding_registry",
                        lambda: None)
    monkeypatch.setattr(dispatcher.DependencyManager,
                        "should_load_cx_dependencies", lambda: False)
    monkeypatch.setattr(dispatcher.DependencyManager, "is_in_linux_consumption",
                        lambda: False)
    instance = dispatcher.Dispatcher.__new__(dispatcher.Dispatcher)
    instance._request_id = "init"
    instance._host = "127.0.0.1"
    instance._azure_monitor_available = False
    instance._otel_libs_available = False
    yield instance
    with host_configuration.reset_host_configuration():
        pass


def request(capabilities=None):
    return protos.StreamingMessage(
        worker_init_request=protos.WorkerInitRequest(
            capabilities=capabilities or {},
            function_app_directory="host-supplied-not-worker-local"))


@pytest.mark.asyncio
@pytest.mark.parametrize("source,status,expected", [
    (b"{}", protos.HostConfiguration.Available, b"{}"),
    (b'/*c*/ { "a": [1,], }', protos.HostConfiguration.Available, b'{"a":[1]}'),
    (b"", protos.HostConfiguration.Available, b""),
    (b"{invalid-json", protos.HostConfiguration.Error, b""),
    (None, protos.HostConfiguration.Missing, b""),
    (b"\xff", protos.HostConfiguration.Error, b""),
    (b"x" * 65537, protos.HostConfiguration.TooLarge, b""),
], ids=("available", "jsonc", "empty", "malformed-json", "missing", "error",
        "too-large"))
async def test_classic_init_preserves_status_capabilities_and_snapshot(
        worker, tmp_path, source, status, expected):
    if source is not None:
        (tmp_path / "host.json").write_bytes(source)
    baseline = (await worker._handle__worker_init_request(
        request())).worker_init_response
    assert not baseline.HasField("host_configuration")
    assert host_configuration._snapshot is None
    message = await worker._handle__worker_init_request(
        request({"HostConfiguration": "1"}))
    response = protos.StreamingMessage.FromString(
        message.SerializeToString()).worker_init_response
    assert response.result.status == protos.StatusResult.Success
    assert response.capabilities == baseline.capabilities
    assert response.worker_metadata == baseline.worker_metadata
    assert response.host_configuration.status == status
    assert response.host_configuration.content == expected
    (tmp_path / "host.json").write_bytes(b"replacement")
    message.worker_init_response.host_configuration.content = b"mutated"
    # A new dispatcher still belongs to the same process/application generation.
    replacement = dispatcher.Dispatcher.__new__(dispatcher.Dispatcher)
    replacement.__dict__.update(worker.__dict__)
    repeated = await replacement._handle__worker_init_request(
        request({"HostConfiguration": "1"}))
    assert repeated.worker_init_response.host_configuration == (
        response.host_configuration)


@pytest.mark.asyncio
async def test_existing_indexing_error_remains_deferred(
        worker, tmp_path, monkeypatch):
    (tmp_path / "host.json").write_bytes(b"{}")
    monkeypatch.setattr(dispatcher, "is_envvar_true",
                        lambda key: key == "PYTHON_ENABLE_INIT_INDEXING")
    error = RuntimeError("indexing failed")
    with patch.object(worker, "load_function_metadata", side_effect=error):
        response = await worker._handle__worker_init_request(
            request({"HostConfiguration": "1"}))
    assert worker._function_metadata_exception is error
    assert response.worker_init_response.result.status == protos.StatusResult.Success
    assert response.worker_init_response.host_configuration.content == b"{}"


@pytest.mark.asyncio
async def test_existing_http_server_failure_is_not_swallowed(
        worker, tmp_path, monkeypatch):
    (tmp_path / "host.json").write_bytes(b"{}")
    monkeypatch.setattr(dispatcher, "is_envvar_true",
                        lambda key: key == "PYTHON_ENABLE_INIT_INDEXING")
    with patch.object(worker, "load_function_metadata"), \
            patch.object(dispatcher.HttpV2Registry, "http_v2_enabled",
                         return_value=True), \
            patch.object(dispatcher, "initialize_http_server",
                         side_effect=dispatcher.HttpServerInitError("http")), \
            pytest.raises(dispatcher.HttpServerInitError):
        await worker._handle__worker_init_request(
            request({"HostConfiguration": "1"}))


@pytest.mark.asyncio
async def test_classic_specialization_invalidates_cached_failure(
        worker, tmp_path):
    (tmp_path / "host.json").write_bytes(b"\xff")
    response = await worker._handle__worker_init_request(
        request({"HostConfiguration": "1"}))
    assert response.worker_init_response.host_configuration.status == (
        protos.HostConfiguration.Error)
    next_app = tmp_path / "next"
    next_app.mkdir()
    (next_app / "host.json").write_bytes(b'"new"')
    reload_request = protos.StreamingMessage(
        function_environment_reload_request=(
            protos.FunctionEnvironmentReloadRequest(environment_variables={
                "FUNCTIONS_APPLICATION_DIRECTORY": str(next_app)})))
    with patch.dict(os.environ), \
            patch.object(dispatcher.time, "tzset", create=True), \
            patch.object(worker, "_stop_sync_call_tp"), \
            patch.object(worker, "_create_sync_call_tp", return_value=Mock()), \
            patch.object(dispatcher.DependencyManager,
                         "reload_customer_libraries"):
        result = await worker._handle__function_environment_reload_request(
            reload_request)
        assert result.function_environment_reload_response.result.status == (
            protos.StatusResult.Success)
        assert host_configuration._snapshot is None
        response = await worker._handle__worker_init_request(
            request({"HostConfiguration": "1"}))
        assert response.worker_init_response.host_configuration.content == b'"new"'
