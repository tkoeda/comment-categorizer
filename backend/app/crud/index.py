from datetime import datetime, timezone
from typing import Optional

from app.models.index import Index, IndexJob
from app.models.users import User
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


async def create_index_job(db: AsyncSession, industry_id: int, user: User) -> str:
    """Create a new index job and return its ID"""
    try:
        job = IndexJob(industry_id=industry_id, status="pending", user_id=user.id)
        db.add(job)
        await db.commit()
        return job.id
    except Exception:
        await db.rollback()
        raise


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: str,
    user: Optional[User] = None,
    error: Optional[str] = None,
    reviews_included: Optional[int] = None,
    progress: Optional[float] = None,
):
    """Update the status of a job"""
    try:
        if user is None:
            index_job = await get_index_job(db, job_id)
        else:
            index_job = await get_index_job(db, job_id, user)

        if index_job:
            index_job.status = status
            if error:
                index_job.error = error
            if reviews_included is not None:
                index_job.reviews_included = reviews_included
            if progress is not None:
                index_job.progress = progress
            index_job.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


async def delete_all_index_jobs(db: AsyncSession, user: User):
    # Delete all index jobs
    try:
        stmt = select(IndexJob).filter(IndexJob.user_id == user.id)
        result = await db.execute(stmt)
        jobs = result.scalars().all()
        for job in jobs:
            await db.delete(job)
            await db.commit()
    except Exception:
        await db.rollback()
        raise


async def get_index_job(db: AsyncSession, job_id: int, user: Optional[User] = None):
    stmt = select(IndexJob).filter(IndexJob.id == job_id)
    if user:
        stmt = stmt.filter(IndexJob.user_id == user.id)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_index_job(db: AsyncSession, user: User):
    stmt = select(IndexJob).filter(
        IndexJob.status.in_(["pending", "processing"]), IndexJob.user_id == user.id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_index(db: AsyncSession, industry_id: int, user: User):
    stmt = select(Index).filter(
        Index.industry_id == industry_id, Index.user_id == user.id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_index(db: AsyncSession, industry_id: int, user: User):
    try:
        stmt = select(Index).filter(
            Index.industry_id == industry_id, Index.user_id == user.id
        )
        result = await db.execute(stmt)
        index = result.scalar_one_or_none()

        if index:
            await db.delete(index)
            await db.commit()
            return True
        else:
            return False
    except SQLAlchemyError:
        await db.rollback()
        raise
