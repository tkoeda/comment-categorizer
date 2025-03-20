import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import uvicorn
from app.core.config import Settings
from app.core.database import Base, async_engine
from app.core.routes import router as api_router
from app.events import register_event_listeners
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich.console import Console

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before 'yield' runs on application startup.
    Code after 'yield' runs on application shutdown.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    register_event_listeners()
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
