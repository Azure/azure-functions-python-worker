# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Example FastAPI application for testing the FastAPI runtime
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Create FastAPI app
app = FastAPI(title="Example FastAPI on Azure Functions")


# Models
class Item(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    price: float


class User(BaseModel):
    username: str
    email: str


# In-memory storage
items_db: List[Item] = []
users_db: List[User] = []


# Routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to FastAPI on Azure Functions!",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/items")
async def list_items():
    """List all items"""
    return {"items": items_db, "count": len(items_db)}


@app.get("/items/{item_id}")
async def get_item(item_id: int):
    """Get a specific item by ID"""
    for item in items_db:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/items")
async def create_item(item: Item):
    """Create a new item"""
    if item.id is None:
        item.id = len(items_db) + 1
    items_db.append(item)
    return {"status": "created", "item": item}


@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item):
    """Update an existing item"""
    for idx, existing_item in enumerate(items_db):
        if existing_item.id == item_id:
            item.id = item_id
            items_db[idx] = item
            return {"status": "updated", "item": item}
    raise HTTPException(status_code=404, detail="Item not found")


@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    """Delete an item"""
    for idx, item in enumerate(items_db):
        if item.id == item_id:
            items_db.pop(idx)
            return {"status": "deleted", "item_id": item_id}
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/users")
async def list_users():
    """List all users"""
    return {"users": users_db, "count": len(users_db)}


@app.post("/users")
async def create_user(user: User):
    """Create a new user"""
    users_db.append(user)
    return {"status": "created", "user": user}


# This demonstrates a synchronous route (less common in FastAPI but supported)
@app.get("/sync-example")
def sync_route():
    """Example of a synchronous route"""
    return {"type": "sync", "message": "This is a synchronous route"}
