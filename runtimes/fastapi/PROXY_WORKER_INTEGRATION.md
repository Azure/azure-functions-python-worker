# FastAPI Runtime - Proxy Worker Integration Guide

## Overview

This document explains how the FastAPI runtime integrates with the proxy worker to enable native FastAPI support in Azure Functions Python Worker.

## Integration Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                  Azure Functions Host                          │
│                  (gRPC Server)                                 │
└─────────────────────────┬─────────────────────────────────────┘
                          │
                          │ gRPC Protocol
                          │ (StreamingMessage)
                          │
┌─────────────────────────▼─────────────────────────────────────┐
│                     Proxy Worker                               │
│              (workers/proxy_worker/)                           │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Request Router                                           │ │
│  │  ────────────────                                         │ │
│  │  if is_fastapi_app():                                     │ │
│  │      import azure_functions_fastapi               │ │
│  │      runtime.worker_init_request(...)                     │ │
│  │  elif is_v2_app():                                        │ │
│  │      import azure_functions_runtime                       │ │
│  │      runtime.worker_init_request(...)                     │ │
│  │  elif is_v1_app():                                        │ │
│  │      import azure_functions_runtime_v1                    │ │
│  │      runtime.worker_init_request(...)                     │ │
│  └──────────────────────┬───────────────────────────────────┘ │
└─────────────────────────┼─────────────────────────────────────┘
                          │
                          │ Python Import
                          │
       ┌──────────────────┼──────────────────┬──────────────────┐
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐
│   FastAPI    │  │    V2        │  │    V1        │  │  Future    │
│   Runtime    │  │   Runtime    │  │   Runtime    │  │  Runtimes  │
│  (NEW!)      │  │  (Existing)  │  │  (Existing)  │  │            │
└──────────────┘  └──────────────┘  └──────────────┘  └────────────┘
```

## Detection Logic

The proxy worker needs to detect which runtime to use for a given app.

### Option 1: Environment Variable
```python
# In proxy worker
runtime_type = os.environ.get("PYTHON_RUNTIME_TYPE", "auto")

if runtime_type == "fastapi":
    from azure_functions_fastapi import (
        worker_init_request,
        functions_metadata_request,
        invocation_request,
        function_load_request,
        function_environment_reload_request
    )
elif runtime_type == "v2":
    from azure_functions_runtime import (...)
elif runtime_type == "v1":
    from azure_functions_runtime_v1 import (...)
elif runtime_type == "auto":
    # Auto-detect
    runtime_module = detect_runtime()
```

### Option 2: Auto-Detection
```python
# In proxy worker
def detect_runtime():
    """Detect which runtime to use based on function_app.py"""
    try:
        # Try to import the user's module
        import importlib
        module = importlib.import_module("function_app")
        
        # Check for FastAPI app
        from fastapi import FastAPI
        for attr_name in dir(module):
            if isinstance(getattr(module, attr_name), FastAPI):
                return "fastapi"
        
        # Check for V2 app
        from azure.functions import FunctionRegister
        for attr_name in dir(module):
            if isinstance(getattr(module, attr_name), FunctionRegister):
                return "v2"
        
        # Default to V1
        return "v1"
    except Exception:
        return "v1"  # Fallback to V1
```

## Proxy Worker Changes

### 1. Import Statement
```python
# At top of proxy worker main file
import os
from typing import Optional

# Runtime imports (conditional)
runtime_handlers = None

def load_runtime():
    """Load appropriate runtime based on detection"""
    global runtime_handlers
    
    runtime_type = os.environ.get("PYTHON_RUNTIME_TYPE", "auto")
    
    if runtime_type == "auto":
        runtime_type = detect_runtime()
    
    if runtime_type == "fastapi":
        import azure_functions_fastapi as runtime
        runtime_handlers = {
            "worker_init": runtime.worker_init_request,
            "functions_metadata": runtime.functions_metadata_request,
            "function_load": runtime.function_load_request,
            "invocation": runtime.invocation_request,
            "function_environment_reload": runtime.function_environment_reload_request,
        }
    elif runtime_type == "v2":
        import azure_functions_runtime as runtime
        runtime_handlers = {
            "worker_init": runtime.worker_init_request,
            "functions_metadata": runtime.functions_metadata_request,
            "function_load": runtime.function_load_request,
            "invocation": runtime.invocation_request,
            "function_environment_reload": runtime.function_environment_reload_request,
        }
    # ... handle v1, etc.
    
    return runtime_type
```

### 2. Request Routing
```python
# In proxy worker request handler
async def handle_request(request):
    """Route request to appropriate runtime handler"""
    global runtime_handlers
    
    if not runtime_handlers:
        load_runtime()
    
    request_type = request.request.WhichOneof("request")
    
    if request_type == "worker_init_request":
        return await runtime_handlers["worker_init"](request)
    elif request_type == "function_metadata_request":
        return await runtime_handlers["functions_metadata"](request)
    elif request_type == "function_load_request":
        return await runtime_handlers["function_load"](request)
    elif request_type == "invocation_request":
        return await runtime_handlers["invocation"](request)
    elif request_type == "function_environment_reload_request":
        return await runtime_handlers["function_environment_reload"](request)
    else:
        # Handle other request types...
        pass
```

## Environment Variables

### Configuration
```bash
# Force FastAPI runtime
PYTHON_RUNTIME_TYPE=fastapi

# Auto-detect (default)
PYTHON_RUNTIME_TYPE=auto

# Specify function app file (if not function_app.py)
PYTHON_SCRIPT_FILE_NAME=my_app.py
```

### In host.json
```json
{
  "version": "2.0",
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  },
  "functionTimeout": "00:05:00",
  "logging": {
    "logLevel": {
      "default": "Information"
    }
  },
  "extensions": {
    "http": {
      "routePrefix": ""
    }
  }
}
```

### In local.settings.json
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "PYTHON_RUNTIME_TYPE": "fastapi",
    "PYTHON_SCRIPT_FILE_NAME": "function_app.py"
  }
}
```

## Request Flow

### 1. Worker Init
```python
# Host sends WorkerInitRequest
request = {
    "request_id": "abc-123",
    "worker_init_request": {
        "capabilities": {...}
    }
}

# Proxy worker routes to FastAPI runtime
response = await azure_functions_fastapi.worker_init_request(request)

# FastAPI runtime:
# 1. Indexes FastAPI app
# 2. Discovers all routes
# 3. Converts to Azure Functions
# 4. Returns capabilities

# Response sent back to host
```

### 2. Function Metadata
```python
# Host sends FunctionMetadataRequest
request = {
    "request_id": "def-456",
    "function_metadata_request": {}
}

# Proxy worker routes to FastAPI runtime
response = await azure_functions_fastapi.functions_metadata_request(request)

# FastAPI runtime returns metadata for all discovered routes
# Each route is represented as an Azure Function

# Response:
{
    "function_metadata_results": [
        {
            "name": "get_hello",
            "function_id": "get_hello",
            "bindings": {
                "req": {...},
                "$return": {...}
            },
            ...
        },
        {
            "name": "post_users",
            ...
        }
    ]
}
```

### 3. Invocation
```python
# Host sends InvocationRequest for HTTP request
request = {
    "request_id": "ghi-789",
    "invocation_request": {
        "invocation_id": "inv-123",
        "function_id": "get_hello",
        "input_data": [
            {
                "http": {
                    "method": "GET",
                    "url": "http://localhost:7071/hello",
                    ...
                }
            }
        ]
    }
}

# Proxy worker routes to FastAPI runtime
response = await azure_functions_runtime.invocation_request(request)

# FastAPI runtime:
# 1. Looks up function metadata
# 2. Gets route handler reference
# 3. Executes FastAPI route handler
# 4. Formats response

# Response:
{
    "invocation_id": "inv-123",
    "return_value": {
        "http": {
            "status_code": "200",
            "body": '{"message": "Hello"}',
            "headers": {...}
        }
    },
    "result": {
        "status": "Success"
    }
}
```

## Proxy Worker Code Example

```python
# workers/proxy_worker/main.py (example)
import asyncio
import os
from typing import Optional, Dict, Callable

class ProxyWorker:
    def __init__(self):
        self.runtime_handlers: Optional[Dict[str, Callable]] = None
        self.runtime_type: Optional[str] = None
    
    def load_runtime(self):
        """Load the appropriate runtime"""
        runtime_type = os.environ.get("PYTHON_RUNTIME_TYPE", "auto")
        
        if runtime_type == "auto":
            runtime_type = self._detect_runtime()
        
        if runtime_type == "fastapi":
            import azure_functions_runtime as runtime
        elif runtime_type == "v2":
            import azure_functions_runtime as runtime
        else:
            import azure_functions_runtime_v1 as runtime
        
        self.runtime_handlers = {
            "worker_init": runtime.worker_init_request,
            "functions_metadata": runtime.functions_metadata_request,
            "function_load": runtime.function_load_request,
            "invocation": runtime.invocation_request,
            "function_environment_reload": runtime.function_environment_reload_request,
        }
        
        self.runtime_type = runtime_type
        print(f"Loaded runtime: {runtime_type}")
    
    def _detect_runtime(self) -> str:
        """Auto-detect runtime type"""
        try:
            import importlib
            import sys
            
            # Add current directory to path
            if os.getcwd() not in sys.path:
                sys.path.insert(0, os.getcwd())
            
            # Import function_app.py
            module = importlib.import_module("function_app")
            
            # Check for FastAPI
            try:
                from fastapi import FastAPI
                for attr_name in dir(module):
                    attr = getattr(module, attr_name, None)
                    if isinstance(attr, FastAPI):
                        return "fastapi"
            except ImportError:
                pass
            
            # Check for V2
            try:
                from azure.functions import FunctionRegister
                for attr_name in dir(module):
                    attr = getattr(module, attr_name, None)
                    if isinstance(attr, FunctionRegister):
                        return "v2"
            except ImportError:
                pass
            
        except Exception as e:
            print(f"Error detecting runtime: {e}")
        
        return "v1"  # Default
    
    async def handle_request(self, request):
        """Handle incoming request from host"""
        if not self.runtime_handlers:
            self.load_runtime()
        
        # Extract request type
        request_type = request.request.WhichOneof("request")
        
        # Route to appropriate handler
        if request_type == "worker_init_request":
            return await self.runtime_handlers["worker_init"](request)
        elif request_type == "function_metadata_request":
            return await self.runtime_handlers["functions_metadata"](request)
        elif request_type == "function_load_request":
            return await self.runtime_handlers["function_load"](request)
        elif request_type == "invocation_request":
            return await self.runtime_handlers["invocation"](request)
        elif request_type == "function_environment_reload_request":
            return await self.runtime_handlers["function_environment_reload"](request)
        else:
            raise ValueError(f"Unknown request type: {request_type}")

# Usage
worker = ProxyWorker()

async def main():
    # Receive request from host
    request = await receive_from_host()
    
    # Handle request
    response = await worker.handle_request(request)
    
    # Send response back to host
    await send_to_host(response)
```

## Testing Integration

### Unit Test
```python
# Test proxy worker runtime loading
def test_fastapi_runtime_loading():
    """Test that proxy worker can load FastAPI runtime"""
    os.environ["PYTHON_RUNTIME_TYPE"] = "fastapi"
    
    worker = ProxyWorker()
    worker.load_runtime()
    
    assert worker.runtime_type == "fastapi"
    assert worker.runtime_handlers is not None
    assert "worker_init" in worker.runtime_handlers
```

### Integration Test
```python
# Test full request flow
async def test_full_request_flow():
    """Test complete request flow through proxy worker"""
    # Set up
    os.environ["PYTHON_RUNTIME_TYPE"] = "fastapi"
    worker = ProxyWorker()
    
    # Create mock WorkerInitRequest
    request = create_mock_worker_init_request()
    
    # Handle request
    response = await worker.handle_request(request)
    
    # Verify response
    assert response.worker_init_response.result.status == "Success"
```

## Benefits of This Architecture

1. **Separation of Concerns**: Each runtime is self-contained
2. **Easy Extension**: Add new runtimes without changing proxy worker core
3. **Runtime-Specific Optimizations**: Each runtime can optimize for its framework
4. **Backward Compatibility**: V1 and V2 runtimes continue to work
5. **Testability**: Each runtime can be tested independently

## Next Steps

1. **Implement in Proxy Worker**:
   - Add runtime detection logic
   - Add runtime loading mechanism
   - Add request routing

2. **Testing**:
   - Unit tests for detection logic
   - Integration tests for request flow
   - End-to-end tests with actual FastAPI apps

3. **Documentation**:
   - Update proxy worker docs
   - Add FastAPI runtime setup guide
   - Create migration guide

4. **Performance**:
   - Benchmark against V2 runtime
   - Optimize hot paths
   - Profile cold start time

## Summary

The FastAPI runtime integrates seamlessly with the proxy worker by:
- Exposing the same interface as V2 runtime (event handlers)
- Being detected automatically or via environment variable
- Handling all worker protocol events
- Converting FastAPI routes to Azure Functions transparently

This allows developers to deploy FastAPI apps to Azure Functions with zero code changes!
