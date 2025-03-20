from fastapi import HTTPException
from models.models import Industry
from sqlalchemy.orm import Session


def create_industry(db: Session, name: str):
    """Create a new industry."""
    existing_industry = db.query(Industry).filter(Industry.name == name).first()
    if existing_industry:
        return None

    industry = Industry(name=name)
    db.add(industry)
    db.commit()
    db.refresh(industry)
    return industry


def get_industry(db: Session, industry_id: int):
    """Retrieve an industry by its ID."""
    return db.query(Industry).filter(Industry.id == industry_id).first()


def delete_industry(db: Session, industry_id: int):
    """Delete an industry by ID."""
    industry = get_industry(db, industry_id)
    if not industry:
        return False

    try:
        db.delete(industry)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error deleting industry: {str(e)}"
        )


def get_industries(db: Session):
    """Retrieve all industries with their categories."""
    industries = db.query(Industry).all()
    return [
        {
            "id": industry.id,
            "name": industry.name,
            "categories": [category.name for category in industry.categories],
        }
        for industry in industries
    ]
