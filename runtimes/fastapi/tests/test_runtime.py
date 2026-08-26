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
    FunctionMetadataResponse = ProtoMessage
    StatusResult = StatusResult


def test_runtime_exports_package_version():
    assert VERSION == PACKAGE_VERSION


@pytest.mark.asyncio
async def test_metadata_request_loads_and_caches_metadata(
    tmp_path, monkeypatch
):
    (tmp_path / "function_app.py").touch()
    monkeypatch.chdir(tmp_path)

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

    response = await handle_event.functions_metadata_request(None)

    assert loader_args == (
        str(tmp_path / "function_app.py"),
        str(tmp_path),
        Protos,
    )
    assert handle_event._fastapi_app is app
    assert handle_event._metadata_result is metadata
    assert handle_event._converter is converter
    assert response.function_metadata_results is metadata
    assert response.result.status == StatusResult.Success
