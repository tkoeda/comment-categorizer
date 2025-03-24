import asyncio
import logging
import os

from app.auth.dependencies import get_current_user
from app.constants import (
    DATA_DIR,
)
from app.core.database import AsyncSessionLocal, get_db
from app.crud.index import create_index_job, get_index, get_index_job
from app.crud.industries import get_industry
from app.crud.reviews import (
    get_review,
)
from app.models.users import User
from app.schemas.index import (
    IndexStatusResponse,
    UpdatePastReviewsIndexRequest,
)
from app.utils.routers.index import (
    process_index_job,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

REVIEWS_DIR = os.path.join(DATA_DIR, "reviews")
NEW_RAW_DIR = os.path.join(REVIEWS_DIR, "new", "raw")
NEW_COMBINED_DIR = os.path.join(REVIEWS_DIR, "new", "combined")
NEW_CLEANED_DIR = os.path.join(REVIEWS_DIR, "new", "cleaned")
PAST_RAW_DIR = os.path.join(REVIEWS_DIR, "past", "raw")
PAST_COMBINED_DIR = os.path.join(REVIEWS_DIR, "past", "combined")
PAST_CLEANED_DIR = os.path.join(REVIEWS_DIR, "past", "cleaned")
FINAL_DIR = os.path.join(REVIEWS_DIR, "final")


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
        industry = await get_industry(db, industry_id)
        if not industry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found"
            )

        index = await get_index(db, industry_id)

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
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.post("/update_past_reviews_index")
async def update_past_reviews_index_endpoint(
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

    try:
        if request.mode not in ["add", "replace"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode must be 'add' or 'replace'",
            )

        industry = await get_industry(db, request.industry_id)
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
        job_id = await create_index_job(db, request.industry_id)

        asyncio.create_task(
            process_index_job(
                job_id=job_id,
                industry_id=request.industry_id,
                past_cleaned_id=request.past_cleaned_id,
                mode=request.mode,
            ),
            name=f"job{job_id}",
        )
        return {
            "message": f"Index {'replacement' if request.mode == 'replace' else 'update'} job scheduled",
            "job_id": job_id,
            "status": "pending",
        }
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.get("/index_job_status/{job_id}")
async def check_index_job_status(
    job_id: str,
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
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.websocket("/ws/index_job/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    job_id: int,
):
    await websocket.accept()
    try:
        logger.debug(f"WebSocket connection established for job {job_id}")
        async with AsyncSessionLocal() as db:
            last_status = None

            while True:
                db.expire_all()
                job = await get_index_job(db, job_id)
                if job is None:
                    logger.error(f"Job {job_id} not found")
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close()
                    break
                logger.debug(f"Checking job {job_id}, status: {job.status}")
                current_status = job.status

                if current_status != last_status:
                    logger.debug(
                        f"Status changed from {last_status} to {current_status}"
                    )
                    response = {
                        "job_id": job.id,
                        "status": job.status,
                        "updated_at": job.updated_at.isoformat(),
                    }
                    if job.status == "completed":
                        response["reviews_included"] = job.reviews_included
                    if job.status == "failed":
                        response["error"] = job.error
                    await websocket.send_json(response)
                    last_status = current_status
                if job.status in ["completed", "failed"]:
                    logger.debug(f"WebSocket connection closed for job {job_id}")
                    await websocket.close()
                    break

                await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"WebSocket for job {job_id} disconnected")
    except SQLAlchemyError as e:
        await websocket.send_json({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error in WebSocket for job {job_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        try:
            await websocket.send_json({"error": "An unexpected error occurred"})
        except:
            pass
    finally:
        logger.debug(f"WebSocket connection closed for job {job_id}")
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task() and task.get_name().startswith(
                f"job{job_id}"
            ):
                task.cancel()
