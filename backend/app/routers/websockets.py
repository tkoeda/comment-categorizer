import asyncio
import logging

from app.common.job_registry import running_review_jobs
from app.core.database import AsyncSessionLocal
from app.crud.index import get_index_job
from app.utils.routers.jobs import get_review_job
from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/index_job/{job_id}")
async def index_job_websocket(
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
                    logger.error(
                        f"Job {job_id} disappeared from database during monitoring"
                    )
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close()
                    return
                current_status = job.status
                logger.debug(
                    f"Current job {job_id} status: {current_status}, progress: {job.progress}"
                )
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
                if job.status in ["completed", "failed", "cancelled"]:
                    logger.debug(f"WebSocket connection closed for job {job_id}")
                    await websocket.close()
                    break

                await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"WebSocket for job {job_id} disconnected")
    except SQLAlchemyError as e:
        await websocket.send_json({"error": f"データベースエラー: {str(e)}"})
    except Exception as e:
        logger.error(f"Error in WebSocket for job {job_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        try:
            await websocket.send_json({"error": "予期しないエラーが発生しました。"})
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    finally:
        logger.debug(f"WebSocket connection closed for job {job_id}")
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task() and task.get_name().startswith(
                f"index_job{job_id}"
            ):
                task.cancel()


@router.websocket("/review_job/{job_id}")
async def review_job_websocket(
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
                job = await get_review_job(db, job_id)
                if job is None:
                    logger.error(f"Job {job_id} not found")
                    await websocket.send_json({"error": "Job not found"})
                    await websocket.close()
                    return

                logger.debug(f"Checking job {job_id}, status: {job.status}")
                current_status = job.status
                logger.debug(
                    f"Current job {job_id} status: {current_status}, progress: {job.progress}"
                )
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
                        response["final_review_id"] = job.final_review_id
                    if job.status == "failed":
                        response["error"] = job.error
                    await websocket.send_json(response)
                    last_status = current_status
                if job.status in ["completed", "failed", "cancelled"]:
                    logger.debug(f"WebSocket connection closed for job {job_id}")
                    await websocket.close()
                    break

                await asyncio.sleep(2)

    except WebSocketDisconnect:
        logger.info(f"WebSocket for job {job_id} disconnected")
    except SQLAlchemyError as e:
        await websocket.send_json({"error": f"データベースエラー: {str(e)}"})
    except Exception as e:
        logger.error(f"Error in WebSocket for job {job_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        try:
            await websocket.send_json({"error": "予期しないエラーが発生しました。"})
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}")
    finally:
        logger.debug(f"WebSocket connection closed for job {job_id}")
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task() and task.get_name().startswith(
                f"review_job{job_id}"
            ):
                task.cancel()
