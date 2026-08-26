import json

import pytest
from fastapi import FastAPI

from azure_functions_fastapi.converter import FastAPIConverter
from azure_functions_fastapi.handler import execute_fastapi_route
from azure_functions_fastapi.indexer import FastAPIIndexer


class MockAzureRequest:
    method = "GET"
    headers = {}
    params = {}
    route_params = {}

    def __init__(self, url):
        self.url = url

    def get_body(self):
        return b""


def test_indexes_default_documentation_routes():
    functions = FastAPIIndexer(FastAPI()).index_routes()

    routes = {
        (function.name, function.route_path): set(function.http_methods)
        for function in functions
    }

    assert routes == {
        ("fastapi_openapi", "/openapi.json"): {"GET", "HEAD"},
        ("fastapi_swagger_ui_html", "/docs"): {"GET", "HEAD"},
        (
            "fastapi_swagger_ui_redirect",
            "/docs/oauth2-redirect",
        ): {"GET", "HEAD"},
        ("fastapi_redoc_html", "/redoc"): {"GET", "HEAD"},
    }


def test_respects_custom_and_disabled_documentation_routes():
    app = FastAPI(
        openapi_url="/schema.json",
        docs_url="/swagger",
        redoc_url=None,
        swagger_ui_oauth2_redirect_url="/swagger/oauth2-redirect",
    )

    functions = FastAPIIndexer(app).index_routes()

    assert {function.route_path for function in functions} == {
        "/schema.json",
        "/swagger",
        "/swagger/oauth2-redirect",
    }


def test_documentation_function_ids_do_not_collide_with_user_endpoints():
    app = FastAPI()

    @app.get("/custom-openapi")
    async def openapi():
        return {"custom": True}

    converter = FastAPIConverter()
    functions = converter.convert_to_azure_functions(
        FastAPIIndexer(app).index_routes())

    assert converter.get_function("fastapi_openapi").route_path == \
        "/openapi.json"
    assert converter.get_function("openapi").route_path == "/custom-openapi"
    assert len(functions) == 5


@pytest.mark.asyncio
async def test_documentation_handlers_use_functions_route_prefix():
    app = FastAPI(title="Documentation Test")
    functions = {
        function.route_path: function
        for function in FastAPIIndexer(app).index_routes()
    }

    openapi_function = functions["/openapi.json"]
    openapi_response = await execute_fastapi_route(
        app,
        MockAzureRequest("http://localhost:7071/api/openapi.json"),
        openapi_function.route_handler,
        openapi_function.route_path,
        openapi_function.is_async,
    )
    assert openapi_response["status_code"] == 200
    assert openapi_response["headers"]["content-type"] == "application/json"
    assert json.loads(openapi_response["body"])["servers"] == [
        {"url": "/api"}
    ]

    docs_function = functions["/docs"]
    docs_response = await execute_fastapi_route(
        app,
        MockAzureRequest("http://localhost:7071/api/docs"),
        docs_function.route_handler,
        docs_function.route_path,
        docs_function.is_async,
    )
    assert docs_response["status_code"] == 200
    assert "url: '/api/openapi.json'" in docs_response["body"]
    assert (
        "window.location.origin + '/api/docs/oauth2-redirect'"
        in docs_response["body"]
    )

    redirect_function = functions["/docs/oauth2-redirect"]
    redirect_response = await execute_fastapi_route(
        app,
        MockAzureRequest(
            "http://localhost:7071/api/docs/oauth2-redirect"),
        redirect_function.route_handler,
        redirect_function.route_path,
        redirect_function.is_async,
    )
    assert redirect_response["status_code"] == 200
    assert "Swagger UI: OAuth2 Redirect" in redirect_response["body"]

    redoc_function = functions["/redoc"]
    redoc_response = await execute_fastapi_route(
        app,
        MockAzureRequest("http://localhost:7071/api/redoc"),
        redoc_function.route_handler,
        redoc_function.route_path,
        redoc_function.is_async,
    )
    assert redoc_response["status_code"] == 200
    assert 'spec-url="/api/openapi.json"' in redoc_response["body"]
