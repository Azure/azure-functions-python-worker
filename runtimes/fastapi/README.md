# Azure Functions FastAPI Runtime

This package provides a runtime adapter to run FastAPI applications natively in Azure Functions Python Worker.

## Overview

The FastAPI runtime enables you to deploy existing FastAPI applications to Azure Functions without modifying your FastAPI code. The runtime:

1. Discovers FastAPI routes in your application
2. Converts each route to an Azure Function with HTTP trigger
3. Handles request forwarding between Azure Functions and FastAPI
4. Preserves FastAPI's request/response handling

## Usage

### Basic Example

Create a `function_app.py` with your FastAPI app:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
async def hello():
    return {"message": "Hello from FastAPI on Azure Functions!"}

@app.post("/users")
async def create_user(name: str):
    return {"user": name, "status": "created"}
```

The runtime will automatically discover these routes and create corresponding Azure Functions.

## Architecture

- **Indexer**: Scans FastAPI app routes and generates function metadata
- **Converter**: Transforms FastAPI routes into Azure Functions structure
- **Handler**: Routes Azure Functions invocations to FastAPI
- **Request/Response Adapter**: Converts between Azure Functions and ASGI formats

## Requirements

- Python 3.9+
- FastAPI 0.100.0+
- Azure Functions Python Worker

## Installation

```bash
pip install azure-functions-fastapi-runtime
```

## Development Status

This is currently a prototype/alpha release for testing FastAPI integration with Azure Functions.
