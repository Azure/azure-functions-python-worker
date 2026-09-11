from fastapi import APIRouter


router = APIRouter()


@router.get("/unregistered")
async def unregistered_route():
    return {"registered": False}
