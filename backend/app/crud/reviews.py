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


async def delete_review(db: AsyncSession, review_id: int):
    """Delete a file record by ID."""
    stmt = select(Review).filter(Review.id == review_id)
    result = await db.execute(stmt)
    review_file = result.scalar_one_or_none()

    if review_file:
        await db.delete(review_file)
        await db.commit()
        return True
    return False


async def delete_review_cascade_up(
    db: AsyncSession, id: int, user_id: int = None
) -> bool:
    """Delete a review and cascade deletion upward to its ancestors."""
    review = await get_review(db, id=id, user_id=user_id)
    if not review:
        return False

    parent_id = review.parent_id

    await db.delete(review)
    await db.flush()

    while parent_id is not None:
        # Get the parent
        parent_stmt = select(Review).filter(Review.id == parent_id)
        parent_result = await db.execute(parent_stmt)
        parent = parent_result.scalar_one_or_none()

        if not parent:
            break

        # Store the next parent ID before potentially deleting
        next_parent_id = parent.parent_id

        # Refresh the parent to ensure we have the latest data
        await db.refresh(parent)
        children_stmt = select(Review).filter(Review.parent_id == parent_id)
        children_result = await db.execute(children_stmt)
        remaining_children = children_result.scalars().all()

        # Check if the parent has any remaining children
        if not remaining_children:
            print("Deleting parent review")
            await db.delete(parent)
            await db.flush()
            parent_id = next_parent_id
        else:
            print("Parent review has other children, stopping cascading")
            break

    await db.commit()
    return True
