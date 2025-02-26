# industry_api.py
from fastapi import APIRouter, HTTPException, Body
import json

router = APIRouter()
DATA_FILE = "industry_categories.json"


def load_industries():
    print("here")
    """Load industries from JSON file or return an empty dictionary if missing."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except FileNotFoundError:
        return {}
    except json.decoder.JSONDecodeError as e:
        print(f"Error decoding JSON from {DATA_FILE}: {e}")
        return {}


def save_industries(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/")
async def get_industries():
    """Return the current industries and their categories."""
    return load_industries()


@router.post("/")
async def add_industry(name: str = Body(..., embed=True), categories: list[str] = Body(..., embed=True)):
    """Add a new industry with its categories."""
    data = load_industries()
    if name in data:
        raise HTTPException(status_code=400, detail="Industry already exists")
    data[name] = categories
    save_industries(data)
    return {"message": f"Industry '{name}' added successfully", "data": data}


@router.delete("/{name}")
async def delete_industry(name: str):
    """Delete an industry and its categories."""
    data = load_industries()
    if name not in data:
        raise HTTPException(status_code=404, detail="Industry not found")
    del data[name]
    save_industries(data)
    return {"message": f"Industry '{name}' deleted successfully", "data": data}


@router.put("/{name}/categories")
async def update_categories(name: str, categories: list[str] = Body(..., embed=True)):
    """Update the categories for an existing industry."""
    data = load_industries()
    if name not in data:
        raise HTTPException(status_code=404, detail="Industry not found")
    data[name] = categories
    save_industries(data)
    return {"message": f"Categories for '{name}' updated successfully", "data": data}
