import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

from app.common.constants import CACHE_DIR, INDEX_DIR
from app.common.job_registry import running_retrievers
from app.core.database import AsyncSessionLocal
from app.crud.index import delete_index, get_index, get_index_job, update_job_status
from app.crud.industries import get_industry
from app.crud.reviews import delete_review_cascade_up, get_review
from app.models.index import Index, IndexJob
from app.models.users import User
from app.rag_pipeline.indexer import FaissRetriever
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def process_index_job(
    job_id: str,
    industry_id: int,
    past_cleaned_id: int,
    mode: str,
    user: User,
):
    """Process the index job in the background"""
    # Create a database session for this background task
    async with AsyncSessionLocal() as db:
        retriever = None
        temp_dir = None
        operation_success = False
        error_msg = None
        try:
            temp_dir = tempfile.mkdtemp(prefix=f"index_job_{job_id}_")
            # Update job status to processing
            await update_job_status(db, job_id, "processing")
            industry = await get_industry(db, industry_id, user=user)

            if not industry:
                logger.error(f"Industry with ID: {industry_id}not found")
                await update_job_status(
                    db,
                    job_id,
                    "failed",
                    user=user,
                    error="Industry not found",
                )
                return

            past_review = await get_review(db, id=past_cleaned_id)
            if not past_review:
                logger.error(f"Review with ID: {past_cleaned_id} not found")
                await update_job_status(
                    db, job_id, "failed", user=user, error="Review not found"
                )
                return

            replace = mode == "replace"
            embeddings_model = "pkshatech/GLuCoSE-base-ja-v2"  # Default model
            old_index = await get_index(db, industry_id, user=user)

            # ADD TO EXISTING INDEX CASE
            if old_index and os.path.exists(old_index.index_path) and not replace:
                retriever = await FaissRetriever.create(
                    industry=industry,
                    db=db,
                    embeddings_model=old_index.embeddings_model,
                )
                running_retrievers[job_id] = retriever
                operation_success = await retriever.update_index(
                    new_past_excel_path=past_review.file_path,
                    db=db,
                    replace=False,
                )
                if not operation_success:
                    if retriever.cancel_requested:
                        error_msg = "ユーザーによりキャンセルされました"
                        await update_job_status(
                            db,
                            job_id,
                            "cancelled",
                            user=user,
                            error=error_msg,
                        )
                    else:
                        error_msg = "Failed to update index"
                    return
            else:
                # REPLACE OR CREATE NEW INDEX CASE
                if old_index and replace:
                    # REPLACEMENT CASE - Create a new instance with temporary paths
                    # Create the retriever with standard configuration
                    retriever = await FaissRetriever.create(
                        industry=industry,
                        db=None,  # No DB yet - we'll handle DB operations manually
                        past_excel_path=past_review.file_path,
                        embeddings_model=embeddings_model,
                    )

                    # Store original paths
                    original_index_path = retriever.index_path
                    original_cache_path = retriever.cache_path

                    # Create temporary file paths in our dedicated temp directory
                    temp_index_path = os.path.join(
                        temp_dir, f"{industry.name}.index"
                    )
                    temp_cache_path = os.path.join(
                        temp_dir, f"past_reviews_{industry.name}.pkl"
                    )

                    # Override paths to use temporary locations
                    retriever.index_path = temp_index_path
                    retriever.cache_path = temp_cache_path

                    # Ensure parent directories exist
                    os.makedirs(os.path.dirname(temp_index_path), exist_ok=True)
                    os.makedirs(os.path.dirname(temp_cache_path), exist_ok=True)

                    # Register the retriever
                    running_retrievers[job_id] = retriever

                    # Generate index with temporary paths
                    logger.info(
                        f"Generating index with temporary paths in {temp_dir}"
                    )
                    logger.info(f"Temp index path: {temp_index_path}")
                    logger.info(f"Temp cache path: {temp_cache_path}")

                    operation_success = await retriever.generate_index()

                    if not operation_success:
                        if retriever.cancel_requested:
                            error_msg = "ユーザーによりキャンセルされました"
                            await update_job_status(
                                db,
                                job_id,
                                "cancelled",
                                user=user,
                                error=error_msg,
                            )
                        else:
                            error_msg = "Failed to create temporary index"
                        return

                    # Update the existing database record instead of creating a new one
                    # This avoids the unique constraint violation
                    now = datetime.now(timezone.utc)
                    old_index.index_path = (
                        original_index_path  # Keep the original path
                    )
                    old_index.cached_data_path = (
                        original_cache_path  # Keep the original path
                    )
                    old_index.embeddings_model = embeddings_model
                    old_index.reviews_included = len(retriever.documents)
                    old_index.updated_at = now

                    # Commit the updated record - no need to delete old one
                    await db.commit()

                    # Delete old files if they exist
                    if os.path.exists(original_index_path):
                        logger.info(
                            f"Deleting old index file: {original_index_path}"
                        )
                        os.remove(original_index_path)
                    if os.path.exists(original_cache_path):
                        logger.info(
                            f"Deleting old cache file: {original_cache_path}"
                        )
                        os.remove(original_cache_path)

                    # Ensure parent directories of final paths exist
                    os.makedirs(
                        os.path.dirname(original_index_path),
                        exist_ok=True,
                    )
                    os.makedirs(
                        os.path.dirname(original_cache_path),
                        exist_ok=True,
                    )

                    # Copy temp files to final locations (using copy2 instead of move for better error handling)
                    logger.info(
                        f"Copying temp index to final location: {temp_index_path} -> {original_index_path}"
                    )
                    shutil.copy2(temp_index_path, original_index_path)

                    logger.info(
                        f"Copying temp cache to final location: {temp_cache_path} -> {original_cache_path}"
                    )
                    shutil.copy2(temp_cache_path, original_cache_path)

                    # Update retriever paths
                    retriever.index_path = original_index_path
                    retriever.cache_path = original_cache_path

                    operation_success = True

                else:
                    # NEW INDEX CASE
                    retriever = await FaissRetriever.create(
                        industry=industry,
                        db=db,  # Pass DB for normal operation
                        past_excel_path=past_review.file_path,
                        embeddings_model=embeddings_model,
                    )
                    running_retrievers[job_id] = retriever

                    # Generate index normally
                    operation_success = await retriever.generate_index()

                    if not operation_success:
                        if retriever.cancel_requested:
                            error_msg = "ユーザーによりキャンセルされました"
                            await update_job_status(
                                db,
                                job_id,
                                "cancelled",
                                user=user,
                                error=error_msg,
                            )
                        else:
                            error_msg = "Failed to create index"
                        return

            # Get updated index info
            # Clean up the retriever from running jobs
            running_retrievers.pop(job_id, None)

            # Get the current index record - this should be the new one
            index = await get_index(db, industry_id, user=user)

            if not index:
                error_msg = f"Index not found for industry {industry_id} after successful operation"
                logger.error(error_msg)
                await update_job_status(
                    db, job_id, "failed", user=user, error=error_msg
                )
                return

            # Mark job as completed
            await update_job_status(
                db,
                job_id,
                "completed",
                user=user,
                reviews_included=index.reviews_included,
            )

            # Only delete the input review after everything is completed successfully
            await delete_review_cascade_up(db, id=past_cleaned_id)

            logger.info(f"Index job {job_id} completed successfully")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing index job: {error_msg}")
            await update_job_status(db, job_id, "failed", user=user, error=error_msg)
        finally:
            # Clean up resources
            if job_id in running_retrievers:
                running_retrievers.pop(job_id, None)

            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.error(f"Failed to clean up temporary directory: {str(e)}")

            # Update job status if there was an error
            if error_msg and not operation_success:
                try:
                    if retriever and retriever.cancel_requested:
                        await update_job_status(
                            db,
                            job_id,
                            "cancelled",
                            user=user,
                            error="ユーザーによりキャンセルされました",
                        )
                    else:
                        await update_job_status(
                            db, job_id, "failed", user=user, error=error_msg
                        )
                except Exception as status_error:
                    logger.error(f"Failed to update job status: {str(status_error)}")


async def get_active_index_job(db: AsyncSession):
    """Get a list of active index jobs."""
    stmt = select(IndexJob).filter(IndexJob.status.in_(["pending", "processing"]))
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return jobs
