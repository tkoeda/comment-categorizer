import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

from app.common.constants import get_user_dirs
from app.common.job_registry import running_review_jobs
from app.core.database import AsyncSessionLocal
from app.crud.industries import get_industry
from app.crud.jobs import get_review_job, update_review_job_status
from app.crud.reviews import create_review, get_review
from app.models.index import Index
from app.models.jobs import ReviewJob
from app.models.users import User
from app.rag_pipeline.data_loader import fetch_new_reviews_from_excel
from app.rag_pipeline.indexer import DummyRetriever, FaissRetriever
from app.utils.routers.reviews import classify_and_merge
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


async def process_review_job(
    job_id: int,
    industry_id: int,
    new_cleaned_id: int,
    use_past_reviews: bool,
    user: User,
):
    """
    Process a review job in the background.
    This handles the entire lifecycle of a review job including retrieval,
    classification, and result generation.
    """
    # Initialize outside the try block so we can reference in finally
    error_msg = None

    try:
        # Initial status update - use dedicated session
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db, job_id, status="processing", user=user
                )
                # No need to commit as update_job_status already does this
            except Exception as e:
                logger.error(f"Failed to update initial job status: {str(e)}")
                raise

        # Get required resources - use dedicated session
        async with AsyncSessionLocal() as db:
            try:
                industry = await get_industry(db, industry_id, user=user)
                if not industry:
                    error_msg = f"Industry with ID: {industry_id} not found"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Store industry data in memory, not in session
                industry_data = {
                    "id": industry.id,
                    "name": industry.name,
                    # Add other needed fields
                }

                # Get the cleaned review
                new_cleaned_review = await get_review(db, id=new_cleaned_id)
                if not new_cleaned_review:
                    error_msg = f"Review with ID: {new_cleaned_id} not found"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Get combined review
                new_combined_review = await get_review(
                    db, id=new_cleaned_review.parent_id
                )
                if not new_combined_review:
                    error_msg = "Combined review not found"
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Store review data for use outside this session
                cleaned_review_data = {
                    "id": new_cleaned_review.id,
                    "file_path": new_cleaned_review.file_path,
                    "display_name": new_cleaned_review.display_name,
                    "parent_id": new_cleaned_review.parent_id,
                }

                combined_review_data = {
                    "id": new_combined_review.id,
                    "file_path": new_combined_review.file_path,
                }
            except Exception as e:
                error_msg = str(e)
                raise

        # Check file existence
        if not os.path.exists(cleaned_review_data["file_path"]):
            error_msg = "New cleaned review file not found on disk"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        if not os.path.exists(combined_review_data["file_path"]):
            error_msg = "Combined review file not found on disk"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Load new reviews from Excel
        logger.info(f"Loading new reviews from {cleaned_review_data['file_path']}")
        new_reviews = fetch_new_reviews_from_excel(
            excel_path=cleaned_review_data["file_path"],
            default_industry=industry_data["name"],
        )

        # Update job with total reviews count - dedicated session
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db,
                    job_id,
                    status="processing",
                    user=user,
                    progress=10.0,  # Setting some initial progress
                )
            except Exception as e:
                logger.error(f"Failed to update reviews count: {str(e)}")
                raise

        # Initialize retriever (FAISS or Dummy) - dedicated session
        retriever = DummyRetriever()
        if use_past_reviews:
            async with AsyncSessionLocal() as db:
                try:
                    # Check if index exists for this industry
                    stmt = select(Index).filter(
                        Index.industry_id == industry_data["id"]
                    )
                    result = await db.execute(stmt)
                    index_info = result.scalar_one_or_none()

                    if index_info and os.path.exists(index_info.index_path):
                        try:
                            retriever = await FaissRetriever.create(
                                industry=industry,  # This might need to be rebuilt
                                user=user,
                                db=db,
                            )
                            logger.info(
                                f"Using FAISS retriever with {index_info.reviews_included} reviews"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error initializing FAISS retriever: {str(e)}"
                            )
                            retriever = DummyRetriever()
                            logger.info("Falling back to dummy retriever")
                    else:
                        logger.info(
                            "No index found for industry. Using dummy retriever."
                        )
                except Exception as e:
                    logger.error(f"Error querying index: {str(e)}")
                    # Continue with DummyRetriever

        # Process status update - dedicated session
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db,
                    job_id,
                    status="processing",
                    user=user,
                    progress=25.0,  # Update progress
                )
            except Exception as e:
                logger.error(f"Failed to update processing status: {str(e)}")
                # Continue anyway

        # Prepare output paths
        user_dirs = get_user_dirs(user.id)
        final_dir = os.path.join(
            user_dirs["final"]["processed"], industry_data["name"]
        )
        os.makedirs(final_dir, exist_ok=True)

        # Generate output path
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_filename = f"{industry_data['name']}_{timestamp}_final.xlsx"
        output_excel_path = os.path.join(final_dir, output_filename)

        # Track the job in running_review_jobs registry
        running_review_jobs[job_id] = {
            "status": "processing",
            "progress": 30.0,
            "cancel_requested": False,
            "total_reviews": len(new_reviews),
            "reviews_processed": 0,
        }
        # Update progress before starting review classification
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db, job_id, status="processing", user=user, progress=30.0
                )
            except Exception as e:
                logger.error(f"Failed to update progress status: {str(e)}")

        # Process reviews
        logger.info(f"Starting review classification for job {job_id}")

        # Process the reviews
        await classify_and_merge(
            industry=industry,  # This might need reconstruction
            new_reviews=new_reviews,
            retriever=retriever,
            new_combined_path=combined_review_data["file_path"],
            new_cleaned_path=cleaned_review_data["file_path"],
            use_past_reviews=use_past_reviews,
            user_api_key=user.openai_api_key,
            output_path=output_excel_path,
        )

        # Update progress after classification
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db,
                    job_id,
                    status="processing",
                    user=user,
                    progress=80.0,  # Classification complete
                )
            except Exception as e:
                logger.error(f"Failed to update progress status: {str(e)}")

        # Set display name
        final_display_name = cleaned_review_data["display_name"].replace(
            "Cleaned", "Final"
        )

        # Create the final review in database - dedicated session
        final_review_id = None
        async with AsyncSessionLocal() as db:
            try:
                final_review = await create_review(
                    db,
                    industry_id=industry_data["id"],
                    review_type="final",
                    display_name=final_display_name,
                    stage="final",
                    file_path=output_excel_path,
                    parent_id=cleaned_review_data["id"],
                    user_id=user.id,
                )
                final_review_id = final_review.id
                await db.commit()
            except Exception as e:
                error_msg = f"Failed to create final review: {str(e)}"
                logger.error(error_msg)
                raise

        # Update job as completed - dedicated session
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db,
                    job_id,
                    status="completed",
                    user=user,
                    progress=100.0,
                )
            except Exception as e:
                error_msg = f"Failed to update completion status: {str(e)}"
                logger.error(error_msg)
                raise

        logger.info(f"Review job {job_id} completed successfully")

    except asyncio.CancelledError:
        logger.info(f"Review job {job_id} was cancelled")

        # Update as cancelled - dedicated session
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db,
                    job_id,
                    status="cancelled",
                    user=user,
                    error="ユーザーによりキャンセルされました",
                )
            except Exception as e:
                logger.error(f"Failed to update cancellation status: {str(e)}")

    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"Error processing review job {job_id}: {error_msg}", exc_info=True
        )

        # Update as failed - dedicated session
        async with AsyncSessionLocal() as db:
            try:
                await update_review_job_status(
                    db, job_id, status="failed", user=user, error=error_msg
                )
            except Exception as inner_e:
                logger.error(f"Failed to update error status: {str(inner_e)}")

    finally:
        # Clean up resources
        if job_id in running_review_jobs:
            running_review_jobs.pop(job_id, None)


async def get_active_review_jobs(db: AsyncSession):
    """Get all active review jobs."""
    stmt = select(ReviewJob).filter(ReviewJob.status.in_(["pending", "processing"]))
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return jobs


async def cancel_review_job(job_id: int, user: User) -> bool:
    """
    Cancel a running review job.
    Returns True if successfully cancelled, False otherwise.
    """
    async with AsyncSessionLocal() as db:
        # Get the job
        job = await get_review_job(db, job_id)
        if not job:
            logger.error(f"Review job {job_id} not found for cancellation")
            return False

        # Check if job can be cancelled
        if job.status not in ["pending", "processing"]:
            logger.info(
                f"Review job {job_id} is in state {job.status}, cannot cancel"
            )
            return False

        # If the job is running, request cancellation
        if job_id in running_review_jobs:
            running_review_jobs[job_id]["cancel_requested"] = True
            logger.info(f"Cancellation requested for review job {job_id}")

            # Wait a short time to let any background tasks start their cancellation routine
            await asyncio.sleep(0.2)

            # Update job status in the database
            await update_review_job_status(
                db,
                job_id,
                "cancelled",
                user=user,
                error="ユーザーによりキャンセルされました",
            )
            # Remove the job from the registry after cancellation
            running_review_jobs.pop(job_id, None)

            return True
        else:
            # If job is pending but not yet in the registry, simply mark as cancelled
            await update_review_job_status(
                db,
                job_id,
                "cancelled",
                user=user,
                error="ユーザーによりキャンセルされました",
            )
            return True
