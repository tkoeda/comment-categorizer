# industry_api.py
import json
import logging
import os

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.crud.industries import (
    create_category,
    create_industry,
    delete_industry,
    get_industries,
)
from app.models.industries import Industry
from app.models.users import User
from app.schemas.industries import (
    IndustryCreate,
    IndustryResponse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

router = APIRouter()
DATA_FILE = "industry_categories.json"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")


def save_industries(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save industry data: {str(e)}",
        )


@router.get("/", response_model=list[IndustryResponse])
async def list_industries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current industries and their categories."""
    try:
        industries = await get_industries(db)
        return industries
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


@router.post("/", response_model=IndustryResponse)
async def add_industry(
    industry_data: IndustryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new industry with its categories."""
    try:
        new_industry = await create_industry(
            db, industry_data.name, user_id=current_user.id
        )
        if not new_industry:
            raise HTTPException(status_code=400, detail="Industry already exists")

        # Add categories
        for category_name in industry_data.categories:
            await create_category(
                db, name=category_name, industry_id=new_industry.id
            )

        stmt = (
            select(Industry)
            .options(selectinload(Industry.categories))
            .filter(Industry.id == new_industry.id)
        )
        result = await db.execute(stmt)
        industry_with_categories = result.scalar_one()

        if not industry_with_categories:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Industry not found",
            )

        return IndustryResponse(
            id=industry_with_categories.id,
            name=industry_with_categories.name,
            categories=[
                category.name for category in industry_with_categories.categories
            ],
        )

    except IntegrityError as e:
        logger.error(f"Integrity error in add_industry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not create industry due to data conflict",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error in add_industry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while creating industry",
        )
    except HTTPException:
        # Re-raise HTTP exceptions without modification
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_industry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
        )


@router.delete("/{industry_id}")
async def remove_industry(
    industry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an industry and its categories from the database."""
    try:
        result = await delete_industry(db, industry_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Industry not found"
            )

        return {"message": "Industry deleted successfully"}
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}",
        )
