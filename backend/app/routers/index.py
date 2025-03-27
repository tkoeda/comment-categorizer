import asyncio
import logging
import os
import sys

from app.common.constants import (
    DATA_DIR,
)
from app.common.job_registry import running_retrievers
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.crud.index import create_index_job, get_index, get_index_job
from app.crud.industries import get_industry
from app.crud.reviews import (
    get_review,
)
from app.models.index import IndexJob
from app.models.users import User
from app.schemas.index import (
    IndexStatusResponse,
    UpdatePastReviewsIndexRequest,
)
from app.utils.routers.index import (
    get_active_index_job,
    process_index_job,
    update_job_status,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{industry_id}", response_model=IndexStatusResponse)
async def get_index_status(
    industry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of the FAISS index for an industry.

    Returns information about whether the index exists, how many reviews it contains,
    and when it was last updated.
    """

    try:
        industry = await get_industry(db, industry_id, current_user)
        if not industry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found"
            )

        index = await get_index(db, industry_id, user=current_user)

        if not index:
            return {
                "exists": False,
                "count": 0,
                "lastUpdated": None,
            }

        index_exists = os.path.exists(index.index_path)

        return {
            "exists": index_exists,
            "count": index.reviews_included if index_exists else 0,
            "lastUpdated": index.updated_at.isoformat() if index_exists else None,
        }
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"データベースエラー: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.post("/update_past_reviews_index")
async def create_or_update_past_reviews_index_endpoint(
    request: UpdatePastReviewsIndexRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add new past reviews to the industry's FAISS index or replace the existing index.

    Args:
        industry_id: ID of the industry
        past_cleaned_id: ID of the past cleaned review to add
        mode: "add" to add to existing index, "replace" to create a new index
    """

    job_id = None

    try:
        if request.mode not in ["add", "replace"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'add' or 'replace'",
            )

        industry = await get_industry(db, request.industry_id, current_user)
        if not industry:
            raise HTTPException(status_code=404, detail="Industry not found")

        past_review = await get_review(db, id=request.past_cleaned_id)
        if not past_review:
            raise HTTPException(status_code=404, detail="Past review not found")

        if past_review.review_type != "past" or past_review.stage != "cleaned":
            raise HTTPException(
                status_code=400,
                detail="Selected review must be a cleaned past review",
            )
        existing_jobs = await get_active_index_job(db)
        if existing_jobs:
            raise HTTPException(
                status_code=400,
                detail="An index job is already in progress. Please wait for it to complete before starting a new one.",
            )

        job_id = await create_index_job(db, request.industry_id, current_user)

        asyncio.create_task(
            process_index_job(
                job_id=job_id,
                industry_id=request.industry_id,
                past_cleaned_id=request.past_cleaned_id,
                mode=request.mode,
                user=current_user,
            ),
            name=f"index_job{job_id}",
        )
        return {
            "message": f"Index {'replacement' if request.mode == 'replace' else 'update'} job scheduled",
            "job_id": job_id,
            "status": "pending",
        }
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"データベースエラー: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )
    finally:
        if job_id is not None and sys.exc_info()[0] is not None:
            try:
                await update_job_status(
                    db,
                    job_id,
                    "failed",
                    user=current_user,
                    error=f"{str(sys.exc_info()[1])}",
                )
            except Exception as status_error:
                logger.error(f"Failed to update job status: {str(status_error)}")


@router.get("/index_job_status/{job_id}")
async def check_index_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check the status of an index generation/update job"""
    try:
        job = await get_index_job(db, job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        response = {
            "job_id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }

        if job.status == "completed":
            response["reviews_included"] = job.reviews_included

        if job.status == "failed":
            response["error"] = job.error

        return response

    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"データベースエラー: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.post("/cancel_index_job/{job_id}")
async def cancel_index_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    index_job = await get_index_job(db, job_id)
    if not index_job:
        raise HTTPException(status_code=404, detail="Job not found")

    if index_job.status not in ["pending", "processing"]:
        return {"message": f"Job already in {index_job.status} state, cannot cancel"}

    # Cancel the running retriever if it exists
    if job_id in running_retrievers:
        retriever = running_retrievers[job_id]
        # This will trigger the snapshot restore in the background task
        retriever.cancel()

        # Wait a short time to give the restore process a chance to start
        await asyncio.sleep(0.2)

        # Update job status
        await update_job_status(
            db,
            job_id,
            "cancelled",
            user=current_user,
            error="ユーザーによりキャンセルされました",
        )

        # Remove from running retrievers after cancellation
        running_retrievers.pop(job_id, None)
        return {"message": "Job cancelled and index restored to previous state"}
    else:
        # If job is pending but retriever not started, just mark as cancelled
        await update_job_status(
            db,
            job_id,
            "cancelled",
            user=current_user,
            error="ユーザーによりキャンセルされました",
        )
        return {"message": "プロセスのキャンセルが要求されました。"}


@router.get("/active_index_job")
async def get_active_index_jobs(db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(IndexJob).filter(
            IndexJob.status.in_(["pending", "processing"])
        )
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
        if not job:
            return {"job_id": None, "status": None, "created_at": None}
        response = {
            "job_id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        return response
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"データベースエラー: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )
