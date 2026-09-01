# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test the example FastAPI app indexing
"""
import sys
import os
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from azure_functions_fastapi.indexer import index_fastapi_app, FastAPIIndexer
from azure_functions_fastapi.converter import FastAPIConverter


def test_example_app_indexing():
    """Test indexing the example FastAPI app"""
    # We need to be in the tests directory for imports to work
    original_dir = os.getcwd()
    try:
        test_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(test_dir)
        
        # Add tests dir to path
        if test_dir not in sys.path:
            sys.path.insert(0, test_dir)
        
        # Index the example app
        functions = index_fastapi_app("example_app.py")
        
        # Should have discovered multiple routes
        assert len(functions) > 0
        
        # Check for expected routes
        function_names = [f.name for f in functions]
        
        expected_routes = [
            "root",  # GET /
            "health_check",  # GET /health
            "list_items",  # GET /items
            "create_item",  # POST /items
            "list_users",  # GET /users
            "create_user",  # POST /users
        ]
        
        for expected in expected_routes:
            assert expected in function_names, f"Expected route {expected} not found"
        
        print(f"\nDiscovered {len(functions)} routes:")
        for func in functions:
            print(f"  - {func.name}: {func.http_methods} {func.route_path}")
        
    finally:
        os.chdir(original_dir)


def test_example_app_conversion():
    """Test converting example app to Azure Functions"""
    original_dir = os.getcwd()
    try:
        test_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(test_dir)
        
        if test_dir not in sys.path:
            sys.path.insert(0, test_dir)
        
        # Index and convert
        fastapi_functions = index_fastapi_app("example_app.py")
        
        converter = FastAPIConverter()
        azure_functions = converter.convert_to_azure_functions(fastapi_functions)
        
        assert len(azure_functions) == len(fastapi_functions)
        
        # Verify each function has proper bindings
        for func in azure_functions:
            assert len(func.bindings) == 2
            assert func.bindings[0]['type'] == 'httpTrigger'
            assert func.bindings[1]['type'] == 'http'
            
            # Verify route is properly set
            assert func.route_path
            assert func.http_methods
        
        print(f"\nConverted {len(azure_functions)} Azure Functions:")
        for func in azure_functions:
            print(f"  - {func.name}")
            print(f"      Route: {func.route_path}")
            print(f"      Methods: {func.http_methods}")
            print(f"      Async: {func.is_async}")
        
    finally:
        os.chdir(original_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
