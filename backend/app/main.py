import json
import logging
import logging.config
import os
from contextlib import asynccontextmanager

import uvicorn
from app.core.config import Settings
from app.core.database import AsyncSessionLocal, Base, async_engine
from app.core.routes import router as api_router
from app.events import register_event_listeners
from app.models.index import IndexJob
from app.utils.routers.index import update_job_status
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console
from sqlalchemy import select

logger = logging.getLogger(__name__)

console = Console()


def configure_logging_from_json():
    os.makedirs("logs", exist_ok=True)
    config_path = os.path.join(
        os.path.dirname(__file__), "core", "logging_config.json"
    )
    with open(config_path, "r") as f:
        config = json.load(f)

    logging.config.dictConfig(config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before 'yield' runs on application startup.
    Code after 'yield' runs on application shutdown.
    """
    configure_logging_from_json()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        stmt = select(IndexJob).filter(IndexJob.status == "processing")
        result = await db.execute(stmt)
        orphaned_jobs = result.scalars().all()

        for job in orphaned_jobs:
            await update_job_status(
                db, job.id, "failed", error="Job was interrupted by server restart"
            )

        if orphaned_jobs:
            logger.info(
                f"Reset {len(orphaned_jobs)} orphaned jobs to 'failed' state"
            )

    register_event_listeners(app)
    yield

    print("App shutting down!")


settings = Settings()
app = FastAPI(lifespan=lifespan)
origins = [
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
