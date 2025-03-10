from typing import Optional

from models.models import Review
from sqlalchemy.orm import Session


def get_review(db: Session, review_id: int):
    """Get a review by its ID."""
    return db.query(Review).filter(Review.id == review_id).first()


def create_review(
    db: Session,
    industry_id: int,
    review_type: str,
    display_name: str,
    stage: str,
    file_path: str,
    parent_id: Optional[int] = None,
):
    """Store metadata for an uploaded file."""
    review_file = Review(
        industry_id=industry_id,
        review_type=review_type,
        display_name=display_name,
        stage=stage,
        file_path=file_path,
        parent_id=parent_id,
    )
    db.add(review_file)
    db.commit()
    db.refresh(review_file)
    return review_file


def delete_review(db: Session, review_id: int):
    """Delete a file record by ID."""
    review_file = db.query(Review).filter(Review.id == review_id).first()
    if review_file:
        db.delete(review_file)
        db.commit()
        return True
    return False


def delete_review_cascade_up(db: Session, review_id: int) -> bool:
    """Delete a review and cascade deletion upward to its ancestors."""
    review = get_review(db, review_id)
    if not review:
        return False

    parent = review.parent

    db.delete(review)
    db.flush()

    while parent and len(parent.children) == 0:
        next_parent = parent.parent
        db.delete(parent)
        db.flush()
        parent = next_parent

    db.commit()

    return True
