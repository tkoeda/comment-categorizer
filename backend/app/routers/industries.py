# industry_api.py
import json
import os

from core.database import get_db
from fastapi import APIRouter, Body, Depends, HTTPException
from services.category_service import create_category
from services.industry_service import (
    create_industry,
    delete_industry,
    get_industries,
)
from sqlalchemy.orm import Session

router = APIRouter()
DATA_FILE = "industry_categories.json"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")


# def load_industries():
#     """Load industries from JSON file or return an empty dictionary if missing."""
#     try:
#         with open(DATA_FILE, "r", encoding="utf-8") as f:
#             content = f.read().strip()
#             return json.loads(content) if content else {}
#     except FileNotFoundError:
#         return {}
#     except json.decoder.JSONDecodeError as e:
#         print(f"Error decoding JSON from {DATA_FILE}: {e}")
#         return {}


def save_industries(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/")
async def list_industries(db: Session = Depends(get_db)):
    """Return the current industries and their categories."""
    return get_industries(db)


@router.post("/")
async def add_industry(
    industry_name: str = Body(..., embed=True),
    categories: list[str] = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Add a new industry with its categories."""
    industry = create_industry(db, industry_name)
    if not industry:
        raise HTTPException(status_code=400, detail="Industry already exists")

    # Add categories
    for category_name in categories:
        create_category(db, name=category_name, industry_id=industry.id)

    return {"message": f"Industry '{industry_name}' added successfully"}


@router.delete("/{industry_id}")
async def remove_industry(industry_id: int, db: Session = Depends(get_db)):
    """Delete an industry and its categories from the database."""
    if not delete_industry(db, industry_id):
        raise HTTPException(status_code=404, detail="Industry not found")

    return {"message": "Industry deleted successfully"}


# @router.put("/{name}/categories")
# async def update_categories(
#     name: str, categories: list[str] = Body(..., embed=True)
# ):
#     """Update the categories for an existing industry."""
#     data = load_industries()
#     if name not in data:
#         raise HTTPException(status_code=404, detail="Industry not found")
#     data[name] = categories
#     save_industries(data)
#     return {"message": f"Categories for '{name}' updated successfully", "data": data}
