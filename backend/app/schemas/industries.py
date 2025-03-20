from typing import List

from pydantic import BaseModel


class IndustryCreate(BaseModel):
    name: str
    categories: List[str]


class IndustryResponse(BaseModel):
    id: int
    name: str
    categories: List[str]
