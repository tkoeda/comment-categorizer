from datetime import datetime, timezone
from typing import Optional

from app.models.index import Index, IndexJob
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


async def create_index_job(db: AsyncSession, industry_id: int) -> str:
    """Create a new index job and return its ID"""
    try:
        job = IndexJob(industry_id=industry_id, status="pending")
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
    error: Optional[str] = None,
    reviews_included: Optional[int] = None,
):
    """Update the status of a job"""
    try:
        index_job = await get_index_job(db, job_id)

        if index_job:
            index_job.status = status
            if error:
                index_job.error = error
            if reviews_included is not None:
                index_job.reviews_included = reviews_included
            index_job.updated_at = datetime.now(timezone.utc)
            await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


async def delete_all_index_jobs(db: AsyncSession):
    # Delete all index jobs
    try:
        stmt = select(IndexJob)
        result = await db.execute(stmt)
        jobs = result.scalars().all()
        for job in jobs:
            await db.delete(job)
            await db.commit()
    except Exception:
        await db.rollback()
        raise


async def get_index_job(db: AsyncSession, job_id: int):
    stmt = select(IndexJob).filter(IndexJob.id == job_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_index(db: AsyncSession, industry_id: int):
    stmt = select(Index).filter(Index.industry_id == industry_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_index(db: AsyncSession, industry_id: int):
    try:
        stmt = select(Index).filter(Index.industry_id == industry_id)
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
