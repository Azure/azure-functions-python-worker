from typing import Optional

import azure.functions as func
from fastapi import FastAPI, Response, Body, HTTPException
from pydantic import BaseModel

fast_app = FastAPI()


class Fruit(BaseModel):
    name: str
    description: Optional[str] = None


@fast_app.get("/get_query_param")
async def get_query_param(name: str = "world"):
    return Response(content=f"hello {name}", media_type="text/plain")


@fast_app.post("/post_str")
async def post_str(person: str = Body(...)):
    return Response(content=f"hello {person}", media_type="text/plain")


@fast_app.post("/post_json_return_json_response")
async def post_json_return_json_response(fruit: Fruit):
    return fruit


@fast_app.get("/get_path_param/{id}")
async def get_path_param(id):
    return Response(content=f"hello {id}", media_type="text/plain")


@fast_app.get("/raise_http_exception")
async def raise_http_exception():
    raise HTTPException(status_code=404, detail="Item not found")


app = func.AsgiFunctionApp(app=fast_app,
                           http_auth_level=func.AuthLevel.ANONYMOUS)
