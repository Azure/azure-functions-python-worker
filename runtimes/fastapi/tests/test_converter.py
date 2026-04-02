# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test FastAPI Converter
"""
import pytest

from azure_functions_runtime.converter import FastAPIConverter
from azure_functions_runtime.indexer import FastAPIIndexer
from fastapi import FastAPI


def test_converter_creates_azure_functions():
    """Test that converter creates proper Azure Functions metadata"""
    app = FastAPI()
    
    @app.get("/api/hello")
    def hello():
        return {"message": "hello"}
    
    # Index and convert
    indexer = FastAPIIndexer(app)
    fastapi_functions = indexer.index_routes()
    
    converter = FastAPIConverter()
    azure_functions = converter.convert_to_azure_functions(fastapi_functions)
    
    assert len(azure_functions) == 1
    func = azure_functions[0]
    
    # Check basic properties
    assert func.name == "get_api_hello"
    assert func.route_path == "/api/hello"
    assert func.http_methods == ["GET"]
    
    # Check bindings
    assert len(func.bindings) == 2
    
    # HTTP trigger binding
    trigger = func.bindings[0]
    assert trigger['type'] == 'httpTrigger'
    assert trigger['direction'] == 'in'
    assert trigger['name'] == 'req'
    assert 'get' in trigger['methods']
    assert trigger['route'] == 'api/hello'
    
    # HTTP output binding
    output = func.bindings[1]
    assert output['type'] == 'http'
    assert output['direction'] == 'out'
    assert output['name'] == '$return'


def test_converter_handles_multiple_methods():
    """Test converter handles routes with multiple HTTP methods"""
    app = FastAPI()
    
    @app.api_route("/items", methods=["GET", "POST"])
    def items():
        return {"items": []}
    
    indexer = FastAPIIndexer(app)
    fastapi_functions = indexer.index_routes()
    
    converter = FastAPIConverter()
    azure_functions = converter.convert_to_azure_functions(fastapi_functions)
    
    func = azure_functions[0]
    trigger = func.bindings[0]
    
    # Should have both methods
    assert set(trigger['methods']) == {'get', 'post'}


def test_converter_get_function():
    """Test that converter can retrieve functions by ID"""
    app = FastAPI()
    
    @app.get("/test")
    def test():
        return {}
    
    indexer = FastAPIIndexer(app)
    fastapi_functions = indexer.index_routes()
    
    converter = FastAPIConverter()
    azure_functions = converter.convert_to_azure_functions(fastapi_functions)
    
    # Should be able to retrieve by function_id
    func = converter.get_function(azure_functions[0].function_id)
    assert func is not None
    assert func.name == "get_test"
    
    # Non-existent ID should return None
    assert converter.get_function("nonexistent") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
