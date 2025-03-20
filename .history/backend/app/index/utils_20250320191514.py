import logging
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.constants import INDEX_DIR
from app.core.database import AsyncSessionLocal
from app.industries.service import get_industry
from app.models.index import Index, IndexJob
from app.rag_pipeline.indexer import FaissRetriever
from app.reviews.service import delete_review_cascade_up, get_review
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def create_index_job(db: AsyncSession, industry_id: int) -> str:
    """Create a new index job and return its ID"""
    job = IndexJob(industry_id=industry_id, status="pending")
    db.add(job)
    await db.commit()
    return job.id


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    status: str,
    error: Optional[str] = None,
    reviews_included: Optional[int] = None,
):
    """Update the status of a job"""
    stmt = select(IndexJob).filter(IndexJob.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job:
        job.status = status
        if error:
            job.error = error
        if reviews_included is not None:
            job.reviews_included = reviews_included
        job.updated_at = datetime.now(timezone.utc)
        await db.commit()
    else:
        logger.error(f"Job {job_id} not found when updating status")


async def get_job_status(db: AsyncSession, job_id: int):
    """Get the current status of a job"""
    stmt = select(IndexJob).filter(IndexJob.id == job_id)
    result = await db.execute(stmt)
    print(result)
    return result.scalar_one_or_none()


async def process_index_job(
    job_id: str, industry_id: int, past_cleaned_id: int, mode: str
):
    """Process the index job in the background"""
    # Create a database session for this background task
    async with AsyncSessionLocal() as db:
        try:
            # Update job status to processing
            await update_job_status(db, job_id, "processing")

            industry = await get_industry(db, industry_id)
            past_review = await get_review(db, id=past_cleaned_id)

            replace = mode == "replace"
            embeddings_model = "pkshatech/GLuCoSE-base-ja-v2"  # Default model

            # Check if index already exists
            stmt = select(Index).filter(Index.industry_id == industry_id)
            result = await db.execute(stmt)
            index_info = result.scalar_one_or_none()

            # Logic for add or replace, similar to the original endpoint
            if index_info and os.path.exists(index_info.index_path) and not replace:
                # Add to existing index
                retriever = await FaissRetriever.create(
                    industry=industry,
                    db=db,
                    embeddings_model=index_info.embeddings_model,
                )

                await retriever.update_index(
                    new_past_excel_path=past_review.file_path, db=db, replace=False
                )
            else:
                # Replace or create new index
                if index_info:
                    # Delete old files if they exist
                    if os.path.exists(index_info.index_path):
                        try:
                            os.remove(index_info.index_path)
                        except OSError as e:
                            logger.warning(f"Could not delete old index file: {e}")

                    if os.path.exists(index_info.cached_data_path):
                        try:
                            os.remove(index_info.cached_data_path)
                        except OSError as e:
                            logger.warning(f"Could not delete old cached data: {e}")

                    await db.delete(index_info)
                    await db.commit()

                # Create new index
                os.makedirs(INDEX_DIR, exist_ok=True)
                retriever = await FaissRetriever.create(
                    industry=industry,
                    db=db,
                    past_excel_path=past_review.file_path,
                    embeddings_model=embeddings_model,
                )

            # Get updated index info
            stmt = select(Index).filter(Index.industry_id == industry_id)
            result = await db.execute(stmt)
            index_info = result.scalar_one_or_none()

            # Mark job as completed
            await update_job_status(
                db, job_id, "completed", reviews_included=index_info.reviews_included
            )

            # Clean up the review if needed
            await delete_review_cascade_up(db, id=past_cleaned_id)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing index job: {error_msg}")
            await update_job_status(db, job_id, "failed", error=error_msg)
