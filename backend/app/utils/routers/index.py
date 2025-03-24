import logging
import os

from app.constants import INDEX_DIR
from app.core.database import AsyncSessionLocal
from app.crud.index import delete_index, get_index, update_job_status
from app.crud.industries import get_industry
from app.crud.reviews import delete_review_cascade_up, get_review
from app.rag_pipeline.indexer import FaissRetriever
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


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
            if not industry:
                logger.error(f"Industry with ID: {industry_id}not found")
                await update_job_status(
                    db, job_id, "failed", error="Industry not found"
                )
                return
            past_review = await get_review(db, id=past_cleaned_id)
            if not past_review:
                logger.error(f"Review with ID: {past_cleaned_id} not found")
                await update_job_status(
                    db, job_id, "failed", error="Review not found"
                )
                return

            replace = mode == "replace"
            embeddings_model = "pkshatech/GLuCoSE-base-ja-v2"  # Default model

            # Check if index already exists
            index = await get_index(db, industry_id)

            # Logic for add or replace, similar to the original endpoint
            if index and os.path.exists(index.index_path) and not replace:
                try:
                    # Add to existing index
                    retriever = await FaissRetriever.create(
                        industry=industry,
                        db=db,
                        embeddings_model=index.embeddings_model,
                    )

                    await retriever.update_index(
                        new_past_excel_path=past_review.file_path,
                        db=db,
                        replace=False,
                    )
                except Exception as e:
                    error_msg = f"Failed to update existing index: {str(e)}"
                    logger.error(error_msg)
                    await update_job_status(db, job_id, "failed", error=error_msg)
                    return
            else:
                # Replace or create new index
                if index:
                    # Delete old files if they exist
                    if os.path.exists(index.index_path):
                        try:
                            os.remove(index.index_path)
                        except OSError as e:
                            logger.warning(f"Could not delete old index file: {e}")

                    if os.path.exists(index.cached_data_path):
                        try:
                            os.remove(index.cached_data_path)
                        except OSError as e:
                            logger.warning(f"Could not delete old cached data: {e}")

                    try:
                        await delete_index(db, industry_id)
                    except SQLAlchemyError as e:
                        error_msg = (
                            f"Database error when deleting old index: {str(e)}"
                        )
                        logger.error(error_msg)
                        await update_job_status(
                            db, job_id, "failed", error=error_msg
                        )
                        return
                try:
                    # Create new index
                    os.makedirs(INDEX_DIR, exist_ok=True)
                    retriever = await FaissRetriever.create(
                        industry=industry,
                        db=db,
                        past_excel_path=past_review.file_path,
                        embeddings_model=embeddings_model,
                    )
                except Exception as e:
                    error_msg = f"Failed to create new index: {str(e)}"
                    logger.error(error_msg)
                    await update_job_status(db, job_id, "failed", error=error_msg)
                    return

            # Get updated index info
            try:
                index = await get_index(db, industry_id)

                if not index:
                    error_msg = f"Index not found for industry {industry_id}"
                    logger.error(error_msg)
                    await update_job_status(db, job_id, "failed", error=error_msg)
                # Mark job as completed
                await update_job_status(
                    db, job_id, "completed", reviews_included=index.reviews_included
                )

                # Clean up the review if needed
                await delete_review_cascade_up(db, id=past_cleaned_id)

            except SQLAlchemyError as e:
                error_msg = f"Database error: {str(e)}"
                logger.error(error_msg)
                await update_job_status(db, job_id, "failed", error=error_msg)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing index job: {error_msg}")
            await update_job_status(db, job_id, "failed", error=error_msg)
