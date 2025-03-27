import logging
from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID

from app.models.jobs import ReviewJob
from app.models.users import User
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


async def create_review_job(
    db: AsyncSession,
    industry_id: int,
    user: User,
    new_cleaned_id: int,
    use_past_reviews: bool = True,
) -> ReviewJob:
    """Create a new review job record."""
    try:
        job = ReviewJob(
            industry_id=industry_id,
            user_id=user.id,
            new_cleaned_id=new_cleaned_id,
            use_past_reviews=use_past_reviews,
            status="pending",
            progress=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add(job)
        await db.commit()
        return job
    except Exception:
        await db.rollback()
        raise


async def get_review_job(db: AsyncSession, job_id: int) -> Optional[ReviewJob]:
    """Get a review job by ID."""
    """Get a review job by ID."""
    # Add explicit logging
    logger.info(f"Looking for review job with ID: {job_id}")

    stmt = select(ReviewJob).filter(ReviewJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        logger.info(f"Review job {job_id} not found in database")
    else:
        logger.info(f"Found review job {job_id} with status: {job.status}")

    return job


async def get_active_review_job(db: AsyncSession, user: User):
    stmt = select(ReviewJob).filter(
        ReviewJob.status.in_(["pending", "processing"]), ReviewJob.user_id == user.id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_user_review_jobs(
    db: AsyncSession,
    user_id: Union[UUID, str],
    industry_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[ReviewJob]:
    """Get review jobs for a user with optional filters."""
    query = select(ReviewJob).filter(ReviewJob.user_id == user_id)

    if industry_id is not None:
        query = query.filter(ReviewJob.industry_id == industry_id)

    if status is not None:
        query = query.filter(ReviewJob.status == status)

    query = query.order_by(ReviewJob.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_review_job_status(
    db: AsyncSession,
    job_id: int,
    status: str,
    user: Optional[User] = None,
    progress: Optional[float] = None,
    error: Optional[str] = None,
    reviews_processed: Optional[int] = None,
    total_reviews: Optional[int] = None,
    final_review_id: Optional[int] = None,
) -> Optional[ReviewJob]:
    """Update a review job's status and related fields."""
    try:
        job = await get_review_job(db, job_id)
        if not job:
            return None

        # Update the job fields
        job.status = status
        job.updated_at = datetime.now(timezone.utc)

        if error is not None:
            job.error = error

        if reviews_processed is not None:
            job.reviews_processed = reviews_processed

        if total_reviews is not None:
            job.total_reviews = total_reviews

        if final_review_id is not None:
            job.final_review_id = final_review_id

        await db.commit()
        await db.refresh(job)
        return job
    except SQLAlchemyError:
        await db.rollback()
        raise


async def delete_review_job(db: AsyncSession, job_id: int) -> bool:
    """Delete a review job."""
    job = await get_review_job(db, job_id)
    if not job:
        return False

    await db.delete(job)
    await db.commit()
    return True
