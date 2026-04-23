# FastAPI Runtime Package - Summary

## Overview
This prototype FastAPI runtime package enables native support for FastAPI applications in Azure Functions Python Worker. It follows the same structure as `runtimes/v2` but is specifically designed to handle FastAPI apps.

## Package Structure
```
runtimes/fastapi/
├── pyproject.toml              # Package configuration
├── requirements.txt            # Dependencies
├── README.md                   # Package overview
├── ARCHITECTURE.md             # Detailed architecture documentation
├── USAGE.md                    # User guide and examples
├── azure_functions_fastapi/
│   ├── __init__.py            # Package exports
│   ├── version.py             # Version info
│   ├── handle_event.py        # Main event handler (worker protocol)
│   ├── indexer.py             # FastAPI route discovery
│   ├── converter.py           # Route to Azure Function conversion
│   ├── handler.py             # Request/response handling
│   ├── logging_config.py      # Logging setup
│   ├── bindings/
│   │   └── __init__.py
│   └── utils/
│       └── __init__.py
└── tests/
    ├── __init__.py
    ├── test_indexer.py         # Indexer unit tests
    ├── test_converter.py       # Converter unit tests
    ├── test_example_app.py     # Integration tests
    └── example_app.py          # Sample FastAPI app for testing
```

## Key Components

### 1. indexer.py - Route Discovery
- **Purpose**: Discovers FastAPI app and scans all routes
- **Key Classes**:
  - `FastAPIIndexer`: Main indexer that scans FastAPI routes
  - `FastAPIFunctionMetadata`: Metadata for each discovered route
- **Process**:
  1. Import user's module dynamically
  2. Find FastAPI app instance
  3. Iterate through all routes
  4. Extract route path, HTTP methods, handler, async status

### 2. converter.py - Azure Functions Adapter
- **Purpose**: Converts FastAPI routes to Azure Functions metadata
- **Key Classes**:
  - `FastAPIConverter`: Converts routes to Azure Functions format
  - `AzureFunctionInfo`: Azure Functions-compatible metadata
- **Process**:
  1. Take FastAPI route metadata
  2. Generate HTTP trigger binding for each route
  3. Create HTTP output binding
  4. Build Azure Functions metadata structure

### 3. handler.py - Request/Response Processing
- **Purpose**: Executes FastAPI routes and handles request/response conversion
- **Key Components**:
  - `FastAPIHandler`: Main handler class
  - `execute_fastapi_route()`: Entry point for route execution
- **Process**:
  1. Receive Azure Functions HTTP request
  2. Extract request data
  3. Call FastAPI route handler directly
  4. Format response for Azure Functions

### 4. handle_event.py - Worker Protocol
- **Purpose**: Implements Azure Functions worker protocol for FastAPI
- **Key Functions**:
  - `worker_init_request()`: Initialize runtime, index FastAPI app
  - `functions_metadata_request()`: Return discovered routes as functions
  - `function_load_request()`: Verify function exists
  - `invocation_request()`: Execute route handler
  - `function_environment_reload_request()`: Re-index app

## How It Works

### Initialization Flow
```
1. Worker starts → worker_init_request()
2. Runtime discovers FastAPI app (indexer.py)
3. Routes are scanned and cataloged
4. Routes converted to Azure Functions (converter.py)
5. Metadata cached for fast lookups
```

### Request Execution Flow
```1. HTTP request arrives at Azure Functions host
2. Host identifies target function by route
3. Proxy worker forwards invocation_request()
4. FastAPI runtime looks up route handler
5. Handler executes route (handler.py)
6. Response formatted and returned

```

### Route-to-Function Conversion Example
```python
# User's FastAPI app
@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id}

# Becomes Azure Function:
# Name: get_api_users_user_id
# Trigger: HTTP GET
# Route: api/users/{user_id}
# Handler: Reference to get_user function
```

## Integration with Proxy Worker

The FastAPI runtime is designed to be called by the proxy worker:

```python
# In proxy worker
from azure_functions_fastapi import (
    worker_init_request,
    functions_metadata_request,
    invocation_request,
    # ... other handlers
)

# Proxy worker routes requests to appropriate handler
if is_fastapi_app:
    response = await worker_init_request(request)
```

## Features Implemented

### ✅ Core Features
- Route discovery from FastAPI app
- Conversion to Azure Functions metadata
- HTTP trigger binding generation
- Request/response handling
- Async and sync route support
- Path parameters (`/users/{id}`)
- Query parameters
- Multiple HTTP methods per route
- JSON request/response handling
- Error handling with proper status codes

### ✅ Developer Experience
- Comprehensive documentation (ARCHITECTURE.md, USAGE.md)
- Example FastAPI app
- Unit tests for core components
- Integration tests
- Clear error messages

## Testing

### Unit Tests
- **test_indexer.py**: Tests route discovery, function naming, async detection
- **test_converter.py**: Tests conversion to Azure Functions metadata, binding generation
- **test_example_app.py**: Integration tests with full FastAPI app

### Running Tests
```bash
cd runtimes/fastapi
pip install -e ".[dev]"
pytest tests/ -v
```

## Example Usage

### Simple FastAPI App
```python
# function_app.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello from FastAPI!"}

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id}
```

This automatically creates two Azure Functions:
- `get_root` for `GET /`
- `get_users_user_id` for `GET /users/{user_id}`

## Next Steps

### For Production
1. **Full ASGI Support**: Implement complete ASGI protocol for advanced features
2. **Middleware Support**: Enable FastAPI middleware
3. **Dependency Injection**: Full support for FastAPI dependencies
4. **Background Tasks**: Support FastAPI background tasks
5. **WebSocket Support**: Enable WebSocket routes (if possible in Azure Functions)
6. **Performance Optimization**: Connection pooling, caching, lazy loading

### For Integration
1. **Proxy Worker Integration**: Wire up the FastAPI runtime in proxy worker
2. **Configuration**: Add configuration options for FastAPI-specific settings
3. **Monitoring**: Integration with Azure Monitor and Application Insights
4. **Logging**: FastAPI-aware logging and tracing

### For Testing
1. **End-to-End Tests**: Test with actual Azure Functions host
2. **Performance Tests**: Benchmark against standard Python worker
3. **Compatibility Tests**: Test with various FastAPI features

## Dependencies

- **Python**: 3.9+
- **FastAPI**: 0.100.0+
- **azure-functions**: Latest
- **Development**: pytest, pytest-asyncio, httpx (for testing)

## License

MIT License - Same as Azure Functions Python Worker

## Notes

This is a prototype implementation that demonstrates the core concepts:
1. ✅ FastAPI route discovery (indexer)
2. ✅ Conversion to Azure Functions structure (converter)
3. ✅ Request handling and execution (handler)
4. ✅ Worker protocol implementation (handle_event)

The architecture mimics `runtimes/v2` but is tailored for FastAPI's structure and features. The runtime can be extended to support more advanced FastAPI features as needed.
