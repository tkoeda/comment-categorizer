import logging
from contextlib import asynccontextmanager

import uvicorn
from core.database import engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models.base import Base
from rich.console import Console
from routers.industries import router as industry_router
from routers.reviews import router as reviews_router
from services.events import register_event_listeners

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()

origins = [
    "http://localhost:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before 'yield' runs on application startup.
    Code after 'yield' runs on application shutdown.
    """
    Base.metadata.create_all(bind=engine)
    register_event_listeners()
    yield

    print("App shutting down!")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(industry_router, prefix="/industries", tags=["Industries"])
app.include_router(reviews_router, prefix="/reviews", tags=["Reviews"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
