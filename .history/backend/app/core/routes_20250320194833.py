from app.auth.router import router as session_router
from app.router.industries import router as industry_router
from app.routers.index import router as index_router
from app.routers.reviews import router as review_router
from app.routers.users import router as user_router
from fastapi import APIRouter

version_prefix = "/api/v1"
router = APIRouter()

router.include_router(
    industry_router, prefix=f"{version_prefix}/industries", tags=["Industries"]
)
router.include_router(
    review_router, prefix=f"{version_prefix}/reviews", tags=["Reviews"]
)
router.include_router(user_router, prefix=f"{version_prefix}/users", tags=["Users"])
router.include_router(session_router, prefix=f"{version_prefix}/auth", tags=["Auth"])
router.include_router(index_router, prefix=f"{version_prefix}/index", tags=["Index"])
