from fastapi import FastAPI

from azure_functions_fastapi.indexer import FastAPIIndexer


def test_does_not_index_default_documentation_routes():
    functions = FastAPIIndexer(FastAPI()).index_routes()

    assert functions == []


def test_does_not_index_custom_documentation_routes():
    app = FastAPI(
        openapi_url="/schema.json",
        docs_url="/swagger",
        redoc_url=None,
        swagger_ui_oauth2_redirect_url="/swagger/oauth2-redirect",
    )

    functions = FastAPIIndexer(app).index_routes()

    assert functions == []


def test_user_endpoint_is_indexed_when_documentation_routes_are_present():
    app = FastAPI()

    @app.get("/custom-openapi")
    async def openapi():
        return {"custom": True}

    functions = FastAPIIndexer(app).index_routes()

    assert [(function.name, function.route_path) for function in functions] == [
        ("openapi", "/custom-openapi")
    ]
