from typing import Optional

from app.models.reviews import Review
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload


async def get_review(db: AsyncSession, id: int, user_id: int = None):
    """Get a review by its ID."""
    stmt = select(Review).filter(Review.id == id)
    if user_id:
        stmt = stmt.filter(Review.user_id == user_id)
    stmt = stmt.options(joinedload(Review.parent))
    result = await db.execute(stmt)
    review = result.scalar_one_or_none()
    return review


async def create_review(
    db: AsyncSession,
    industry_id: int,
    review_type: str,
    display_name: str,
    stage: str,
    file_path: str,
    user_id: int,
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
        user_id=user_id,
    )
    db.add(review_file)
    await db.commit()
    await db.refresh(review_file)
    return review_file
