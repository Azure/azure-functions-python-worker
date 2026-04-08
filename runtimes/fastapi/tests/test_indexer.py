# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test FastAPI Indexer
"""
import pytest
from fastapi import FastAPI

from azure_functions_runtime_fastapi.indexer import FastAPIIndexer, index_fastapi_app


def test_indexer_discovers_routes():
    """Test that the indexer can discover FastAPI routes"""
    app = FastAPI()
    
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
    assert "get_hello" in function_names
    assert "post_users" in function_names
    assert "get_items_item_id" in function_names
    
    # Check route paths are preserved
    for func in functions:
        if func.name == "get_hello":
            assert func.route_path == "/hello"
            assert "GET" in func.http_methods
        elif func.name == "post_users":
            assert func.route_path == "/users"
            assert "POST" in func.http_methods


def test_indexer_handles_async_routes():
    """Test that the indexer correctly identifies async routes"""
    app = FastAPI()
    
    @app.get("/sync")
    def sync_route():
        return {"type": "sync"}
    
    @app.get("/async")
    async def async_route():
        return {"type": "async"}
    
    indexer = FastAPIIndexer(app)
    functions = indexer.index_routes()
    
    for func in functions:
        if func.name == "get_sync":
            assert not func.is_async
        elif func.name == "get_async":
            assert func.is_async


def test_indexer_handles_root_path():
    """Test that the indexer handles root path correctly"""
    app = FastAPI()
    
    @app.get("/")
    def root():
        return {"message": "root"}
    
    indexer = FastAPIIndexer(app)
    functions = indexer.index_routes()
    
    assert len(functions) == 1
    assert functions[0].name == "get_root"
    assert functions[0].route_path == "/"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
