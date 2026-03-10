# FastAPI Runtime Architecture

## Overview

The FastAPI runtime enables native support for FastAPI applications in Azure Functions Python Worker. It acts as an adapter layer that discovers FastAPI routes, converts them to Azure Functions, and handles request routing.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure Functions Host                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ gRPC Communication
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     Proxy Worker                             │
│  (workers/proxy_worker/)                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Python Import/Call
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              FastAPI Runtime Package                         │
│         (runtimes/fastapi/)                                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  handle_event.py - Main Event Handler                  │ │
│  │  - worker_init_request()                               │ │
│  │  - functions_metadata_request()                        │ │
│  │  - function_load_request()                             │ │
│  │  - invocation_request()                                │ │
│  └────────────┬──────────────────┬────────────────────────┘ │
│               │                  │                           │
│  ┌────────────▼──────────┐  ┌───▼──────────────────────┐   │
│  │  indexer.py           │  │  converter.py             │   │
│  │  - Find FastAPI app   │  │  - Convert routes to      │   │
│  │  - Scan routes        │  │    Azure Functions        │   │
│  │  - Extract metadata   │  │  - Generate bindings      │   │
│  └───────────────────────┘  └───────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  handler.py - Request/Response Handler                │   │
│  │  - Convert Azure Functions request to ASGI           │   │
│  │  - Execute FastAPI route handler                     │   │
│  │  - Convert response back to Azure Functions format   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Direct Call
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   User's FastAPI App                         │
│                  (function_app.py)                           │
│                                                              │
│  app = FastAPI()                                             │
│                                                              │
│  @app.get("/hello")                                          │
│  async def hello():                                          │
│      return {"message": "Hello"}                             │
└──────────────────────────────────────────────────────────────┘
```

## Request Flow

### 1. Initialization (Worker Init)

```
Host → Proxy Worker → FastAPI Runtime
                      ↓
                   indexer.py
                      ↓
                   Discover FastAPI app
                      ↓
                   Scan all routes
                      ↓
                   converter.py
                      ↓
                   Convert to Azure Functions metadata
```

### 2. Metadata Discovery (Function Metadata Request)

```
Host → Proxy Worker → FastAPI Runtime → Return list of functions
                                        (one per FastAPI route)
```

### 3. Function Invocation (HTTP Request)

```
HTTP Request → Host → Proxy Worker → FastAPI Runtime
                                     ↓
                                  handler.py
                                     ↓
                              Extract Azure Functions request
                                     ↓
                              Call FastAPI route handler
                                     ↓
                              Format response
                                     ↓
Host ← Proxy Worker ← FastAPI Runtime
```

## Key Components

### indexer.py - FastAPI Route Discovery

**Purpose**: Discovers and catalogs all routes in a FastAPI application

**Key Classes**:
- `FastAPIIndexer`: Main indexer class
- `FastAPIFunctionMetadata`: Metadata for each discovered route

**Process**:
1. Import the user's Python module
2. Find the FastAPI app instance
3. Iterate through `app.routes`
4. Extract metadata for each route:
   - Route path (e.g., `/api/users/{id}`)
   - HTTP methods (GET, POST, etc.)
   - Handler function reference
   - Async vs sync

### converter.py - Azure Functions Adapter

**Purpose**: Converts FastAPI route metadata to Azure Functions format

**Key Classes**:
- `FastAPIConverter`: Converts routes to functions
- `AzureFunctionInfo`: Azure Functions metadata structure

**Process**:
1. Take FastAPI route metadata
2. Create HTTP trigger binding for each route
3. Create HTTP output binding
4. Generate function metadata compatible with Python worker

**Binding Structure**:
```python
{
    "name": "req",
    "type": "httpTrigger",
    "direction": "in",
    "methods": ["get"],
    "route": "api/users"
}
```

### handler.py - Request/Response Processing

**Purpose**: Executes FastAPI routes and handles request/response conversion

**Key Functions**:
- `execute_fastapi_route()`: Main execution entry point
- `FastAPIHandler.handle_request()`: Request processing
- `_format_response()`: Response formatting

**Request Flow**:
1. Receive Azure Functions HTTP request
2. Extract relevant data (method, URL, headers, body)
3. Call the FastAPI route handler directly
4. Convert result to Azure Functions response format

### handle_event.py - Event Processing

**Purpose**: Main event handler that responds to Azure Functions worker protocol

**Key Functions**:
- `worker_init_request()`: Initialize runtime, index app
- `functions_metadata_request()`: Return discovered functions
- `function_load_request()`: Load specific function
- `invocation_request()`: Execute function
- `function_environment_reload_request()`: Reload/re-index app

## Data Flow

### Route to Function Conversion

```
FastAPI Route:
  Path: /api/users/{user_id}
  Method: GET
  Handler: async def get_user(user_id: int)

      ↓ (indexer.py)

FastAPIFunctionMetadata:
  name: "get_api_users_user_id"
  route_path: "/api/users/{user_id}"
  http_methods: ["GET"]
  route_handler: <function get_user>
  is_async: True

      ↓ (converter.py)

AzureFunctionInfo:
  name: "get_api_users_user_id"
  bindings: [
    {
      "type": "httpTrigger",
      "direction": "in",
      "methods": ["get"],
      "route": "api/users/{user_id}"
    },
    {
      "type": "http",
      "direction": "out"
    }
  ]

      ↓ (handle_event.py)

RpcFunctionMetadata:
  (protobuf message sent to host)
```

### Request Execution Flow

```
HTTP GET /api/users/123

      ↓

Azure Functions Host
  - Routes to function "get_api_users_user_id"

      ↓

Proxy Worker
  - Forwards invocation request

      ↓

FastAPI Runtime (invocation_request)
  - Looks up function metadata
  - Extracts HTTP request data

      ↓

handler.py (execute_fastapi_route)
  - Calls get_user(user_id=123)
  - Returns result

      ↓

Format Response
  {
    "status_code": 200,
    "headers": {...},
    "body": '{"user": {...}}'
  }

      ↓

Return to Host → HTTP Response
```

## Key Design Decisions

### 1. Direct Handler Invocation
- Routes are executed by calling the FastAPI handler directly
- Bypasses ASGI server for performance
- Simplifies integration with Azure Functions

### 2. Route-to-Function Mapping
- Each FastAPI route becomes a separate Azure Function
- Maintains granular control and monitoring
- Enables per-route configuration

### 3. Metadata-Driven Indexing
- App is indexed once during initialization
- Metadata cached for fast lookups
- Re-indexing supported for hot reload

### 4. Protobuf Communication
- Uses same protocol as standard Python worker
- Seamless integration with host
- No changes needed to Azure Functions infrastructure

## Integration Points

### With Proxy Worker
- Proxy worker imports and calls FastAPI runtime functions
- Uses standard Python function calls (not gRPC internally)
- Passes protobuf objects for requests/responses

### With User's FastAPI App
- Runtime imports user's module dynamically
- Discovers FastAPI app instance via reflection
- Maintains reference to route handlers for invocation

### With Azure Functions Host
- Communicates via gRPC (through proxy worker)
- Uses standard worker protocol
- Reports functions via metadata requests

## Future Enhancements

### 1. Full ASGI Protocol Support
- Implement complete ASGI lifecycle
- Support ASGI middleware
- Enable streaming responses

### 2. Advanced FastAPI Features
- Dependency injection support
- Background tasks
- WebSocket support
- Lifespan events

### 3. Performance Optimizations
- Connection pooling
- Response caching
- Lazy loading of routes

### 4. Development Experience
- Hot reload support
- Better error messages
- FastAPI-specific debugging tools

## Testing Strategy

### Unit Tests
- `test_indexer.py`: Route discovery
- `test_converter.py`: Metadata conversion
- `test_handler.py`: Request/response handling (TODO)

### Integration Tests
- `test_example_app.py`: End-to-end with sample app
- Real FastAPI app indexing and conversion

### Manual Testing
- Deploy to Azure Functions
- Test with actual HTTP requests
- Verify monitoring and logging
