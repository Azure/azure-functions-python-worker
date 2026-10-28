from fastapi import APIRouter

from app.schemas import User


profile_router = APIRouter(prefix="/{user_id}/profile")


@profile_router.get("/")
async def get_user_profile(user_id: int):
    return {"user_id": user_id}


router = APIRouter()


@router.post("/")
async def create_user(user: User):
    return user


router.include_router(profile_router)
