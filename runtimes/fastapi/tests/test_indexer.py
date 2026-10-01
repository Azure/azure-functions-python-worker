# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test FastAPI Indexer
"""
import pytest
from fastapi import FastAPI

from azure_functions_fastapi.indexer import FastAPIIndexer, index_fastapi_app


def test_indexer_discovers_routes():
    """Test that the indexer can discover FastAPI routes"""
    app = FastAPI(openapi_url=None)
    
    @app.get("/hello")
    def hello():
        return {"message": "hello"}
    
    @app.post("/users")
    def create_user():
        return {"status": "created"}
    
    @app.get("/items/{item_id}")
    def get_item(item_id: int):
        return {"item_id": item_id}
    
    # Index the app
    indexer = FastAPIIndexer(app)
    functions = indexer.index_routes()
    
    # Should have discovered 3 routes
    assert len(functions) == 3
    
    # Check function names are generated correctly
    function_names = [f.name for f in functions]
    assert "hello" in function_names
    assert "create_user" in function_names
    assert "get_item" in function_names
    
    # Check route paths are preserved
    for func in functions:
        if func.name == "hello":
            assert func.route_path == "/hello"
            assert "GET" in func.http_methods
        elif func.name == "create_user":
            assert func.route_path == "/users"
            assert "POST" in func.http_methods


def test_indexer_handles_async_routes():
    """Test that the indexer correctly identifies async routes"""
    app = FastAPI(openapi_url=None)
    
    @app.get("/sync")
    def sync_route():
        return {"type": "sync"}
    
    @app.get("/async")
    async def async_route():
        return {"type": "async"}
    
    indexer = FastAPIIndexer(app)
    functions = indexer.index_routes()
    
    functions_by_name = {func.name: func for func in functions}
    assert not functions_by_name["sync_route"].is_async
    assert functions_by_name["async_route"].is_async


def test_indexer_handles_root_path():
    """Test that the indexer handles root path correctly"""
    app = FastAPI(openapi_url=None)
    
    @app.get("/")
    def root():
        return {"message": "root"}
    
    indexer = FastAPIIndexer(app)
    functions = indexer.index_routes()
    
    assert len(functions) == 1
    assert functions[0].name == "root"
    assert functions[0].route_path == "/"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
