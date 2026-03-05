# FastAPI Runtime - Usage Guide

## Quick Start

### 1. Create a FastAPI Application

Create a `function_app.py` file with your FastAPI app:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello from FastAPI on Azure Functions!"}

@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id, "name": f"User {user_id}"}

@app.post("/api/users")
async def create_user(name: str, email: str):
    return {"status": "created", "name": name, "email": email}
```

### 2. How It Works

The FastAPI runtime will:
1. Discover your FastAPI app automatically
2. Scan all defined routes
3. Create an Azure Function for each route
4. Handle routing between Azure Functions and FastAPI

For the example above, it creates three functions:
- `get_root` - Handles `GET /`
- `get_api_users_user_id` - Handles `GET /api/users/{user_id}`
- `post_api_users` - Handles `POST /api/users`

## Supported Features

### ✅ Supported

- **HTTP Methods**: GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- **Path Parameters**: `/users/{user_id}`
- **Query Parameters**: `/search?q=term`
- **Request Body**: JSON, form data
- **Response Types**: JSON, plain text, custom responses
- **Async Routes**: `async def` handlers
- **Sync Routes**: `def` handlers (though async is recommended)
- **Pydantic Models**: Request/response validation
- **Multiple Routes**: Any number of endpoints

### ⚠️ Partially Supported

- **Dependency Injection**: Basic support, advanced features may not work
- **Middleware**: May not work as expected
- **Background Tasks**: Not currently supported
- **WebSockets**: Not supported

### ❌ Not Supported

- **Server Events (SSE)**: Not supported in Azure Functions HTTP model
- **File Uploads**: May have size limitations
- **Streaming Responses**: Limited support

## Examples

### Basic CRUD API

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

app = FastAPI()

class Item(BaseModel):
    id: int
    name: str
    price: float

items: List[Item] = []

@app.get("/items")
async def list_items():
    return {"items": items}

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    for item in items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/items")
async def create_item(item: Item):
    items.append(item)
    return {"status": "created", "item": item}

@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    for idx, existing_item in enumerate(items):
        if existing_item.id == item_id:
            items[idx] = item
            return {"status": "updated", "item": item}
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    for idx, item in enumerate(items):
        if item.id == item_id:
            items.pop(idx)
            return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Item not found")
```

### With Path and Query Parameters

```python
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    include_details: bool = Query(False),
    format: Optional[str] = Query(None)
):
    user = {"id": user_id, "name": f"User {user_id}"}
    
    if include_details:
        user["email"] = f"user{user_id}@example.com"
        user["created_at"] = "2024-01-01"
    
    if format == "simple":
        return {"id": user_id, "name": user["name"]}
    
    return user
```

### With Request Validation

```python
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

app = FastAPI()

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    age: Optional[int] = Field(None, ge=0, le=150)
    bio: Optional[str] = Field(None, max_length=500)

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    age: Optional[int]

@app.post("/users", response_model=UserResponse)
async def create_user(user: CreateUserRequest):
    # Pydantic automatically validates the request
    return UserResponse(
        id=1,
        username=user.username,
        email=user.email,
        age=user.age
    )
```

### Error Handling

```python
from fastapi import FastAPI, HTTPException, status

app = FastAPI()

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item ID must be positive"
        )
    
    if item_id > 1000:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} not found"
        )
    
    return {"item_id": item_id, "name": f"Item {item_id}"}
```

### Multiple HTTP Methods

```python
from fastapi import FastAPI

app = FastAPI()

# Same path, different methods
@app.get("/resource")
async def get_resource():
    return {"method": "GET"}

@app.post("/resource")
async def create_resource():
    return {"method": "POST"}

@app.put("/resource")
async def update_resource():
    return {"method": "PUT"}

@app.delete("/resource")
async def delete_resource():
    return {"method": "DELETE"}
```

## Configuration

### Environment Variables

The runtime respects these environment variables:

- `PYTHON_SCRIPT_FILE_NAME`: Name of the file containing FastAPI app (default: `function_app.py`)
- Standard Azure Functions environment variables for logging, monitoring, etc.

### FastAPI App Configuration

You can configure your FastAPI app as usual:

```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="API running on Azure Functions",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)
```

## Function Naming Convention

The runtime generates function names from your routes:

| Route | HTTP Method | Generated Function Name |
|-------|-------------|------------------------|
| `/` | GET | `get_root` |
| `/users` | GET | `get_users` |
| `/users` | POST | `post_users` |
| `/users/{id}` | GET | `get_users_id` |
| `/api/v1/items` | GET | `get_api_v1_items` |
| `/products-list` | GET | `get_products_list` |

Rules:
- HTTP method is prefixed (lowercase)
- `/` is replaced with `_`
- Path parameters `{param}` have braces removed
- Hyphens `-` are replaced with underscores `_`
- Leading/trailing slashes are trimmed

## Deployment

### Local Development

```bash
# Install dependencies
cd runtimes/fastapi
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

### Deploy to Azure

1. Ensure your `function_app.py` contains your FastAPI app
2. Install the FastAPI runtime package
3. Configure the proxy worker to use the FastAPI runtime
4. Deploy as usual with Azure Functions Core Tools or VS Code

## Troubleshooting

### "Could not find FastAPI app instance"

**Cause**: The runtime couldn't find a FastAPI app in your module.

**Solution**: Ensure you have:
```python
from fastapi import FastAPI
app = FastAPI()  # Must be named 'app' or another name at module level
```

### "More than one FastAPI app instance found"

**Cause**: Multiple FastAPI() instances at module level.

**Solution**: Keep only one FastAPI app instance:
```python
# ❌ Bad
app1 = FastAPI()
app2 = FastAPI()

# ✅ Good
app = FastAPI()
```

### Route Parameters Not Working

**Cause**: Azure Functions needs to parse path parameters.

**Solution**: Ensure your route path uses curly braces:
```python
@app.get("/users/{user_id}")  # ✅ Correct
async def get_user(user_id: int):
    ...
```

### Import Errors

**Cause**: FastAPI or dependencies not installed.

**Solution**:
```bash
pip install fastapi pydantic
```

## Performance Considerations

### Cold Start
- First request after deployment will be slower (cold start)
- FastAPI app is indexed once and cached
- Subsequent requests are fast

### Async vs Sync
- Prefer `async def` for route handlers
- Better performance for I/O-bound operations
- Sync handlers work but may block

### In-Memory State
- Each function instance has its own memory
- Don't rely on in-memory storage for production
- Use external storage (Azure Storage, Cosmos DB, etc.)

## Best Practices

### 1. Use Pydantic Models
```python
from pydantic import BaseModel

class User(BaseModel):
    name: str
    email: str

@app.post("/users")
async def create_user(user: User):
    return {"status": "created", "user": user}
```

### 2. Add Response Models
```python
@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int):
    return get_user_from_db(user_id)
```

### 3. Use Async Handlers
```python
@app.get("/data")
async def get_data():
    # Use async libraries for I/O
    data = await fetch_from_database()
    return data
```

### 4. Handle Errors Properly
```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    item = find_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

### 5. Add Documentation
```python
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    """
    Get a user by ID.
    
    - **user_id**: The ID of the user to retrieve
    
    Returns the user object if found.
    """
    return {"user_id": user_id}
```

## Migration from Standard Azure Functions

If you have existing Azure Functions HTTP triggers, you can migrate to FastAPI:

### Before (Azure Functions)
```python
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="GetUser")
@app.route(route="users/{id}", methods=["GET"])
def get_user(req: func.HttpRequest) -> func.HttpResponse:
    user_id = req.route_params.get('id')
    return func.HttpResponse(
        body='{"user_id": "' + user_id + '"}',
        mimetype="application/json"
    )
```

### After (FastAPI)
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    return {"user_id": user_id}
```

Benefits:
- Cleaner, more Pythonic code
- Automatic request validation
- Built-in documentation (Swagger/ReDoc)
- Type hints for better IDE support
- Larger ecosystem of FastAPI plugins
