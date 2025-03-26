import logging
from typing import Optional

from app.models.reviews import Review
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


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
    try:
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
    except Exception:
        await db.rollback()
        raise


async def delete_review(db: AsyncSession, review_id: int):
    """Delete a file record by ID."""
    try:
        stmt = select(Review).filter(Review.id == review_id)
        result = await db.execute(stmt)
        review_file = result.scalar_one_or_none()

        if review_file:
            await db.delete(review_file)
            await db.commit()
            return True
        return False
    except Exception:
        await db.rollback()
        raise


async def delete_review_cascade_up(
    db: AsyncSession, id: int, user_id: Optional[UUID] = None
) -> bool:
    """
    Delete a review and cascade deletion upward to its ancestors if they have no other children.

    Args:
        db: Database session
        id: ID of the review to delete
        user_id: Optional user ID for permission checking

    Returns:
        True if deletion was successful, False if review not found
    """
    try:
        # Start a nested transaction for safety
        async with db.begin_nested():
            # Get the review to delete
            review = await get_review(db, id=id, user_id=user_id)
            if not review:
                return False

            parent_id = review.parent_id

            # Delete the target review
            await db.delete(review)
            await db.flush()

            # Process parent chain
            deleted_ids = [id]
            while parent_id is not None:
                # Check if parent exists and has no other children
                children_stmt = select(Review).filter(
                    Review.parent_id == parent_id, Review.id.notin_(deleted_ids)
                )
                remaining_children = (
                    (await db.execute(children_stmt)).scalars().all()
                )

                if not remaining_children:
                    # Get parent for deletion and to check next level
                    parent = (
                        await db.execute(
                            select(Review).filter(Review.id == parent_id)
                        )
                    ).scalar_one_or_none()

                    if not parent:
                        break

                    next_parent_id = parent.parent_id

                    # Delete the parent
                    await db.delete(parent)
                    deleted_ids.append(parent_id)
                    parent_id = next_parent_id
                else:
                    # Stop if parent has other children
                    break

        # Commit the transaction
        await db.commit()
        return True

    except Exception as e:
        await db.rollback()
        # Log the exception
        logger.error(f"Error deleting review cascade: {str(e)}")
        raise
