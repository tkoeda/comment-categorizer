from sqlalchemy.orm import Session
from models.models import Category


def create_category(db: Session, name: str, industry_id: int):
    """Create a new category under an industry."""
    category = Category(name=name, industry_id=industry_id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category
