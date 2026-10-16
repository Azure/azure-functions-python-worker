# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys

from azure_functions_fastapi import loader


def test_load_function_metadata_imports_from_function_directory(
    tmp_path, monkeypatch
):
    function_app_directory = tmp_path / "app"
    function_app_directory.mkdir()
    function_path = function_app_directory / "customer_app.py"
    function_path.write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI(openapi_url=None)\n"
        "@app.get('/hello')\n"
        "def hello():\n"
        "    return {'message': 'hello'}\n",
        encoding="utf-8",
    )
    unrelated_directory = tmp_path / "cwd"
    unrelated_directory.mkdir()
    monkeypatch.chdir(unrelated_directory)
    monkeypatch.setattr(
        loader,
        "process_indexed_function",
        lambda protos, app, functions, function_dir: (["metadata"], {}),
    )

    original_sys_path = sys.path.copy()
    try:
        app, metadata, converter = loader.load_function_metadata(
            str(function_path), str(function_app_directory), protos=None)
    finally:
        sys.path[:] = original_sys_path
        sys.modules.pop("customer_app", None)

    assert app.routes[-1].path == "/hello"
    assert metadata == ["metadata"]
    assert converter.get_function("hello").route_path == "/hello"
