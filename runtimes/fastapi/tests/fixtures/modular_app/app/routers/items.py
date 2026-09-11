from fastapi import APIRouter

from app.schemas import Item


router = APIRouter()


@router.get("/")
async def list_items():
    return []


@router.post("/")
async def create_item(item: Item):
    return item
