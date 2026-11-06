from pydantic import BaseModel


class Item(BaseModel):
    name: str


class User(BaseModel):
    name: str
