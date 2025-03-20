import asyncio
import logging
import os

from app.auth.dependencies import get_current_user
from app.constants import (
    DATA_DIR,
)
from app.core.database import AsyncSessionLocal, get_db
from app.index.schemas import (
    IndexStatusResponse,
    UpdatePastReviewsIndexRequest,
)
from app.index.utils import create_index_job, get_job_status, process_index_job
from app.industries.service import get_industry
from app.models.Index import Index
from app.reviews.service import (
    get_review,
)
from app.users.models import User
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logging.basicConfig(level=logging.WARNING)
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
    industry = await get_industry(db, industry_id)
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")

    # Check if industry has an index record
    stmt = select(Index).filter(Index.industry_id == industry_id)
    result = await db.execute(stmt)
    index_info = result.scalar_one_or_none()

    if not index_info:
        return {
            "exists": False,
            "count": 0,
            "lastUpdated": None,
        }

    # Verify index file actually exists
    index_exists = os.path.exists(index_info.index_path)

    return {
        "exists": index_exists,
        "count": index_info.reviews_included if index_exists else 0,
        "lastUpdated": index_info.updated_at.isoformat() if index_exists else None,
    }


@router.post("/update_past_reviews_index")
async def update_past_reviews_index_endpoint(
    request: UpdatePastReviewsIndexRequest,
    background_tasks: BackgroundTasks,
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
    industry_id = request.industry_id
    past_cleaned_id = request.past_cleaned_id
    mode = request.mode
    # Validate inputs
    if mode not in ["add", "replace"]:
        raise HTTPException(
            status_code=400, detail="Mode must be 'add' or 'replace'"
        )

    industry = await get_industry(db, industry_id)
    if not industry:
        raise HTTPException(status_code=404, detail="Industry not found")

    past_review = await get_review(db, id=past_cleaned_id)
    if not past_review:
        raise HTTPException(status_code=404, detail="Past review not found")

    if past_review.review_type != "past" or past_review.stage != "cleaned":
        raise HTTPException(
            status_code=400, detail="Selected review must be a cleaned past review"
        )
    job_id = await create_index_job(db, industry_id)

    # Add the task to run in the background
    background_tasks.add_task(
        process_index_job,
        job_id=job_id,
        industry_id=industry_id,
        past_cleaned_id=past_cleaned_id,
        mode=mode,
    )
    return {
        "message": f"Index {'replacement' if mode == 'replace' else 'update'} job scheduled",
        "job_id": job_id,
        "status": "pending",
    }


@router.get("/index_job_status/{job_id}")
async def check_index_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check the status of an index generation/update job"""
    print("Checking index job status")
    job = await get_job_status(db, job_id)

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


@router.websocket("/ws/index_job/{job_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    job_id: int,
):
    await websocket.accept()
    print(f"WebSocket connection established for job {job_id}")
    try:
        print("WebSocket connection established")
        # Create a new session for this websocket connection
        async with AsyncSessionLocal() as db:
            last_status = None

            # Check status every 2 seconds until job completes or fails
            while True:
                db.expire_all()
                job = await get_job_status(db, job_id)
                if job is None:
                    print(f"Job {job_id} not found")
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close()
                    break
                print(f"Checking job {job_id}, status: {job.status}")
                current_status = job.status

                # Only send updates when the status changes
                if current_status != last_status:
                    print(f"Status changed from {last_status} to {current_status}")
                    response = {
                        "job_id": job.id,
                        "status": job.status,
                        "updated_at": job.updated_at.isoformat(),
                    }
                    if job.status == "completed":
                        response["reviews_included"] = job.reviews_included
                    if job.status == "failed":
                        response["error"] = job.error
                    print("line 205")
                    await websocket.send_json(response)
                    last_status = current_status
                    print("line 208")
                # If the job is completed or failed, close the WebSocket
                if job.status in ["completed", "failed"]:
                    print(f"WebSocket connection closed for job {job_id}")
                    await websocket.close()
                    break

                await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"WebSocket for job {job_id} disconnected")
    except Exception as e:
        print(f"Error in WebSocket for job {job_id}: {str(e)}")
        import traceback

        traceback.print_exc()
    finally:
        print(f"WebSocket connection closed for job {job_id}")
        # Cancel any pending tasks specific to this connection
        # If you have any tasks that were created with asyncio.create_task()
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task() and task.getname().startswith(
                f"job{job_id}"
            ):
                task.cancel()
