# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pytest
from fastapi import FastAPI

from azure_functions_fastapi.handle_event import (
    _get_function_app_script_file,
)
from azure_functions_fastapi.indexer import FastAPIIndexer
from azure_functions_fastapi.utils.constants import PYTHON_SCRIPT_FILE_NAME


@pytest.mark.parametrize(
    ("existing_files", "expected"),
    [
        ([], "function_app.py"),
        (["app.py"], "app.py"),
        (["function_app.py"], "function_app.py"),
        (["app.py", "function_app.py"], "function_app.py"),
    ],
)
def test_get_function_app_script_file(
    tmp_path, monkeypatch, existing_files, expected
):
    monkeypatch.delenv(PYTHON_SCRIPT_FILE_NAME, raising=False)
    for file_name in existing_files:
        (tmp_path / file_name).touch()

    assert _get_function_app_script_file(str(tmp_path)) == expected


def test_configured_script_file_takes_precedence(tmp_path, monkeypatch):
    (tmp_path / "function_app.py").touch()
    (tmp_path / "app.py").touch()
    monkeypatch.setenv(PYTHON_SCRIPT_FILE_NAME, "main.py")

    assert _get_function_app_script_file(str(tmp_path)) == "main.py"


def test_indexer_uses_selected_script_file():
    app = FastAPI()

    @app.get("/")
    def root():
        return {"message": "root"}

    functions = FastAPIIndexer(
        app, function_script_file="app.py").index_routes()

    assert functions[0].function_script_file == "app.py"
