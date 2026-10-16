# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from azure_functions_fastapi import handle_event
from azure_functions_fastapi.runtime import VERSION
from azure_functions_fastapi.version import VERSION as PACKAGE_VERSION


class ProtoMessage:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class StatusResult(ProtoMessage):
    Success = "success"
    Failure = "failure"


class Protos:
    FunctionEnvironmentReloadResponse = ProtoMessage
    FunctionMetadataResponse = ProtoMessage
    StatusResult = StatusResult


def test_runtime_exports_package_version():
    assert VERSION == PACKAGE_VERSION


@pytest.mark.asyncio
async def test_metadata_request_loads_and_caches_metadata(
    tmp_path, monkeypatch
):
    function_app_directory = tmp_path / "app"
    function_app_directory.mkdir()
    (function_app_directory / "function_app.py").touch()
    unrelated_directory = tmp_path / "cwd"
    unrelated_directory.mkdir()
    monkeypatch.chdir(unrelated_directory)

    app = FastAPI()
    metadata = [SimpleNamespace(
        name="root",
        properties={"FastAPIRoute": "/"},
        raw_bindings=[],
    )]
    converter = object()
    loader_args = None

    def load_metadata(function_path, function_dir, protos):
        nonlocal loader_args
        loader_args = (function_path, function_dir, protos)
        return app, metadata, converter

    monkeypatch.setattr(handle_event, "protos", Protos)
    monkeypatch.setattr(handle_event, "_fastapi_app", None)
    monkeypatch.setattr(handle_event, "_metadata_result", None)
    monkeypatch.setattr(handle_event, "_converter", None)
    monkeypatch.setattr(
        handle_event, "load_function_metadata", load_metadata)

    request = SimpleNamespace(request=SimpleNamespace(
        functions_metadata_request=SimpleNamespace(
            function_app_directory=str(function_app_directory))))

    response = await handle_event.functions_metadata_request(request)

    assert loader_args == (
        str(function_app_directory / "function_app.py"),
        str(function_app_directory),
        Protos,
    )
    assert handle_event._fastapi_app is app
    assert handle_event._metadata_result is metadata
    assert handle_event._converter is converter
    assert response.function_metadata_results is metadata
    assert response.result.status == StatusResult.Success


@pytest.mark.asyncio
async def test_environment_reload_uses_request_directory(tmp_path, monkeypatch):
    function_app_directory = tmp_path / "app"
    function_app_directory.mkdir()
    (function_app_directory / "app.py").touch()
    unrelated_directory = tmp_path / "cwd"
    unrelated_directory.mkdir()
    monkeypatch.chdir(unrelated_directory)

    app = FastAPI()
    metadata = [object()]
    converter = object()
    loader_args = None

    def load_metadata(function_path, function_dir, protos):
        nonlocal loader_args
        loader_args = (function_path, function_dir, protos)
        return app, metadata, converter

    request = SimpleNamespace(request=SimpleNamespace(
        function_environment_reload_request=SimpleNamespace(
            function_app_directory=str(function_app_directory))))
    monkeypatch.setattr(handle_event, "protos", Protos)
    monkeypatch.setattr(
        handle_event, "load_function_metadata", load_metadata)
    monkeypatch.setattr(
        handle_event, "get_worker_metadata", lambda protos: object())

    response = await handle_event.function_environment_reload_request(request)

    assert loader_args == (
        str(function_app_directory / "app.py"),
        str(function_app_directory),
        Protos,
    )
    assert handle_event._fastapi_app is app
    assert handle_event._metadata_result is metadata
    assert handle_event._converter is converter
    assert response.result.status == StatusResult.Success
