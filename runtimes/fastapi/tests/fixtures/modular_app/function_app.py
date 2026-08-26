from fastapi import FastAPI

from app.routers import items, root, users


app = FastAPI()
app.include_router(root.router)
app.include_router(items.router, prefix="/items")
app.include_router(users.router, prefix="/users")
