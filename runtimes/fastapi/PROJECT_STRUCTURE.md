# FastAPI Runtime Package - Complete Structure

## Directory Tree
```
runtimes/fastapi/
│
├── 📄 pyproject.toml                    # Package configuration & dependencies
├── 📄 requirements.txt                  # Runtime dependencies
├── 📄 pytest.ini                        # Test configuration
│
├── 📚 Documentation
│   ├── 📄 README.md                     # Overview & quick start
│   ├── 📄 ARCHITECTURE.md               # Detailed architecture & design
│   ├── 📄 USAGE.md                      # User guide with examples
│   └── 📄 IMPLEMENTATION_SUMMARY.md     # Development summary
│
├── 📦 azure_functions_fastapi/  # Main package
│   ├── 📄 __init__.py                   # Package exports
│   ├── 📄 version.py                    # Version info (0.1.0)
│   │
│   ├── 🔧 Core Components
│   │   ├── 📄 handle_event.py           # Worker protocol handler
│   │   ├── 📄 indexer.py                # FastAPI route discovery
│   │   ├── 📄 converter.py              # Route → Azure Function conversion
│   │   └── 📄 handler.py                # Request/response processing
│   │
│   ├── 📄 logging_config.py             # Logging configuration
│   │
│   └── 📁 Submodules
│       ├── 📁 bindings/
│       │   └── 📄 __init__.py
│       └── 📁 utils/
│           └── 📄 __init__.py
│
└── 🧪 tests/                            # Test suite
    ├── 📄 __init__.py
    ├── 📄 test_indexer.py               # Indexer unit tests
    ├── 📄 test_converter.py             # Converter unit tests
    ├── 📄 test_example_app.py           # Integration tests
    └── 📄 example_app.py                # Sample FastAPI app
```

## File Descriptions

### Configuration Files

#### pyproject.toml
- Package metadata (name, version, authors)
- Python version requirement (>=3.9)
- Dependencies: `fastapi>=0.100.0`, `azure-functions`
- Development dependencies: pytest, httpx, etc.
- Build system configuration

#### requirements.txt
- Minimal file pointing to pyproject.toml dependencies
- Used for pip install

#### pytest.ini
- Test discovery configuration
- Asyncio mode for async tests
- Coverage settings
- Test markers (unit, integration, slow)

### Documentation

#### README.md (Package Overview)
- Quick introduction to FastAPI runtime
- High-level overview of features
- Installation instructions
- Basic usage example
- Architecture summary

#### ARCHITECTURE.md (Technical Deep Dive)
- Detailed architecture diagrams
- Component descriptions
- Data flow explanations
- Integration points
- Design decisions
- Future enhancements
- 100+ lines of detailed technical documentation

#### USAGE.md (User Guide)
- Quick start guide
- Feature compatibility matrix
- Multiple code examples (CRUD, validation, etc.)
- Function naming conventions
- Deployment guide
- Troubleshooting section
- Best practices
- Migration guide from standard Azure Functions
- 300+ lines of user-focused documentation

#### IMPLEMENTATION_SUMMARY.md
- Development summary
- Component overview
- Implementation status
- Testing strategy
- Next steps

### Core Runtime Package

#### `__init__.py`
```python
# Exports main event handlers
- worker_init_request
- functions_metadata_request
- function_environment_reload_request
- invocation_request
- function_load_request
- VERSION
```

#### version.py
- Single source of truth for version
- Current: "0.1.0"

#### handle_event.py (200+ lines)
**Purpose**: Main event handler implementing Azure Functions worker protocol

**Functions**:
- `worker_init_request()` - Initialize runtime, discover FastAPI app
- `functions_metadata_request()` - Return all discovered routes as functions
- `function_load_request()` - Verify function exists
- `invocation_request()` - Execute FastAPI route handler
- `function_environment_reload_request()` - Re-index FastAPI app
- `load_function_metadata()` - Internal: Index and convert routes

**Global State**:
- `_converter`: FastAPIConverter instance
- `_fastapi_app`: User's FastAPI app instance
- `_metadata_result`: Cached function metadata
- `protos`: Protobuf definitions

#### indexer.py (130+ lines)
**Purpose**: Discovers FastAPI routes and extracts metadata

**Classes**:
- `FastAPIFunctionMetadata` (NamedTuple)
  - name, function_id, route_path
  - http_methods, function_script_file
  - directory, route_handler, is_async

- `FastAPIIndexer`
  - `index_routes()` - Scan all routes in FastAPI app
  - `_generate_function_name()` - Create unique function name from route

**Function**:
- `index_fastapi_app()` - Entry point to index an app from file path

**Algorithm**:
1. Import module dynamically
2. Find FastAPI() instance via reflection
3. Iterate app.routes
4. Extract APIRoute objects
5. Generate metadata for each route

#### converter.py (90+ lines)
**Purpose**: Converts FastAPI routes to Azure Functions metadata

**Classes**:
- `AzureFunctionInfo` (NamedTuple)
  - name, function_id, directory
  - script_file, entry_point, bindings
  - is_async, route_path, http_methods
  - route_handler

- `FastAPIConverter`
  - `convert_to_azure_functions()` - Convert list of FastAPI routes
  - `get_function()` - Retrieve function by ID

**Binding Generation**:
- Creates httpTrigger binding (input)
- Creates http binding (output)
- Maps HTTP methods
- Preserves route paths

#### handler.py (150+ lines)
**Purpose**: Executes FastAPI routes and handles request/response conversion

**Classes**:
- `ASGIRequest` - Azure Functions request wrapper
- `FastAPIHandler` - Main execution handler

**Functions**:
- `execute_fastapi_route()` - Entry point for route execution
- `handle_request()` - Execute handler and format response
- `_build_scope()` - Create ASGI scope from request
- `_format_response()` - Convert FastAPI response to Azure Functions format

**Response Handling**:
- Supports dict/list (JSON)
- Supports strings (text)
- Supports FastAPI Response objects
- Handles errors with proper status codes

#### logging_config.py
- Configures logger for the package
- Sets up console handler
- Formats log messages

### Test Suite

#### test_indexer.py (80+ lines)
**Tests**:
- `test_indexer_discovers_routes()` - Route discovery
- `test_indexer_handles_async_routes()` - Async detection
- `test_indexer_handles_root_path()` - Root path handling

**Coverage**:
- FastAPIIndexer class
- Function name generation
- Route path extraction
- HTTP method detection

#### test_converter.py (90+ lines)
**Tests**:
- `test_converter_creates_azure_functions()` - Conversion logic
- `test_converter_handles_multiple_methods()` - Multiple HTTP methods
- `test_converter_get_function()` - Function retrieval

**Coverage**:
- FastAPIConverter class
- Binding generation
- Function metadata structure

#### test_example_app.py (80+ lines)
**Tests**:
- `test_example_app_indexing()` - Full app indexing
- `test_example_app_conversion()` - Full conversion pipeline

**Coverage**:
- End-to-end indexing
- End-to-end conversion
- Real-world FastAPI app

#### example_app.py (130+ lines)
**Sample FastAPI Application**:
- Root endpoint
- Health check
- CRUD operations for items
- CRUD operations for users
- Path parameters
- Request validation with Pydantic
- Both async and sync routes
- Error handling

**Routes** (13 total):
- GET / - Root
- GET /health - Health check
- GET /items - List items
- GET /items/{item_id} - Get item
- POST /items - Create item
- PUT /items/{item_id} - Update item
- DELETE /items/{item_id} - Delete item
- GET /users - List users
- POST /users - Create user
- GET /sync-example - Sync route example

## Component Relationships

```
┌─────────────────────────────────────────┐
│         Proxy Worker                     │
│         (calls runtime)                  │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│     handle_event.py                      │
│     (Event Router)                       │
│  ┌───────────────────────────────────┐  │
│  │ worker_init_request() ────────────┼──┼──► indexer.py
│  │ functions_metadata_request()      │  │         │
│  │ invocation_request() ─────────────┼──┼──┐      ▼
│  │ function_load_request()           │  │  │  converter.py
│  │ function_environment_reload()     │  │  │      │
│  └───────────────────────────────────┘  │  │      ▼
└─────────────────────────────────────────┘  │  [Cached Metadata]
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │ handler.py  │
                                      │             │
                                      │ ┌─────────┐ │
                                      │ │ Execute │ │
                                      │ │ FastAPI │ │
                                      │ │ Route   │ │
                                      │ └─────────┘ │
                                      └──────┬──────┘
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │  User's     │
                                      │  FastAPI    │
                                      │  App        │
                                      └─────────────┘
```

## Data Flow

### Route Discovery (Startup)
```
User's FastAPI App (function_app.py)
         │
         ▼
    indexer.py
    - Import module
    - Find FastAPI() instance
    - Scan app.routes
         │
         ▼
FastAPIFunctionMetadata[]
    - One per route
    - Contains: name, path, methods, handler
         │
         ▼
    converter.py
    - For each route, create bindings
    - Generate Azure Functions metadata
         │
         ▼
AzureFunctionInfo[]
    - Compatible with Python worker
    - Ready for execution
         │
         ▼
handle_event.py
    - Cache metadata
    - Store FastAPI app reference
```

### Request Execution (Runtime)
```
HTTP Request
     │
     ▼
Azure Functions Host
     │
     ▼
Proxy Worker
     │
     ▼
handle_event.invocation_request()
     │
     ▼
Look up function metadata
     │
     ▼
handler.execute_fastapi_route()
     │
     ▼
Call FastAPI route handler directly
     │
     ▼
Format response
     │
     ▼
Return to proxy worker
     │
     ▼
HTTP Response
```

## Lines of Code Summary

| File | Lines | Purpose |
|------|-------|---------|
| handle_event.py | ~280 | Worker protocol implementation |
| indexer.py | ~130 | Route discovery |
| converter.py | ~90 | Metadata conversion |
| handler.py | ~150 | Request/response handling |
| ARCHITECTURE.md | ~450 | Technical documentation |
| USAGE.md | ~450 | User guide |
| test_indexer.py | ~80 | Unit tests |
| test_converter.py | ~90 | Unit tests |
| test_example_app.py | ~80 | Integration tests |
| example_app.py | ~130 | Sample app |
| **Total** | **~1,900** | **Complete implementation** |

## Installation & Usage

### Install Package
```bash
cd runtimes/fastapi
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest tests/ -v
```

### Use in Application
```python
# function_app.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
async def hello():
    return {"message": "Hello from FastAPI on Azure Functions!"}
```

The runtime automatically discovers and converts this to an Azure Function.

## Status: ✅ Complete Prototype

All core components implemented:
- ✅ Route discovery (indexer)
- ✅ Metadata conversion (converter)
- ✅ Request handling (handler)
- ✅ Worker protocol (handle_event)
- ✅ Tests (unit + integration)
- ✅ Documentation (architecture + usage)
- ✅ Example app

Ready for integration with proxy worker!
