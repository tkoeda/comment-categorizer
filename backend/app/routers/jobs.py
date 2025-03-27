import asyncio
import logging
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.crud.jobs import create_review_job, get_active_review_job
from app.crud.reviews import get_review
from app.models.industries import Industry
from app.models.jobs import ReviewJob
from app.models.users import User
from app.schemas.jobs import ReviewJobCreate, ReviewJobList, ReviewJobResponse
from app.utils.routers.jobs import cancel_review_job, process_review_job
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/review_jobs",
    status_code=status.HTTP_201_CREATED,
)
async def create_review_job_endpoint(
    request: ReviewJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new review job and start processing it in the background.
    This endpoint initiates the asynchronous processing of reviews.
    """
    # Validate OpenAI API key

    if not current_user.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI APIキーが見つかりません。アカウント設定にAPIキーを追加してください。",
        )

    existing_jobs = await get_active_review_job(db, current_user)
    if existing_jobs:
        raise HTTPException(
            status_code=400,
            detail="An index job is already in progress. Please wait for it to complete before starting a new one.",
        )
    # Validate industry
    industry_result = await db.execute(
        select(Industry).filter(
            Industry.id == request.industry_id, Industry.user_id == current_user.id
        )
    )
    industry = industry_result.scalar_one_or_none()
    if not industry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="業界が見つかりませんでした。",
        )

    # Validate new cleaned review
    new_cleaned_review = await get_review(
        db, id=request.new_cleaned_id, user_id=current_user.id
    )
    if not new_cleaned_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="選択された新しいクリーニング済みファイルが見つかりません。",
        )

    # Create the job
    job = await create_review_job(
        db,
        industry.id,
        current_user,
        new_cleaned_review.id,
        use_past_reviews=request.use_past_reviews,
    )

    asyncio.create_task(
        process_review_job(
            job_id=job.id,
            industry_id=industry.id,
            new_cleaned_id=request.new_cleaned_id,
            use_past_reviews=request.use_past_reviews,
            user=current_user,
        ),
        name=f"review_job{job.id}",
    )
    return {
        "message": f"Review job{job.id} scheduled",
        "job_id": job.id,
        "status": "pending",
    }


@router.get("/active_review_job")
async def get_active_review_jobs(
    db: AsyncSession = Depends(get_db),
):
    """
    Get review job for the current user with optional filtering.
    """
    try:
        stmt = select(ReviewJob).filter(
            ReviewJob.status.in_(["pending", "processing"])
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


@router.get("/status/{job_id}", response_model=ReviewJobResponse)
async def get_review_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the status of a specific review job.
    """
    query = select(ReviewJob).filter(
        ReviewJob.id == job_id, ReviewJob.user_id == current_user.id
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return job


@router.post("/review_jobs/{job_id}/cancel", response_model=ReviewJobResponse)
async def cancel_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a running review job.
    """
    query = select(ReviewJob).filter(
        ReviewJob.id == job_id, ReviewJob.user_id == current_user.id
    )
    result = await db.execute(query)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job cannot be cancelled as it is already {job.status}",
        )

    success = await cancel_review_job(job_id, current_user)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel job",
        )

    # Refresh job data
    await db.refresh(job)

    return job
