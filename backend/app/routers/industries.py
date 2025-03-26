# industry_api.py
import json
import logging
import os

from app.core.database import get_db
from app.core.dependencies import get_current_user
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


@router.get("/", response_model=list[IndustryResponse])
async def list_industries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current industries and their categories."""
    try:
        industries = await get_industries(db, current_user)
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
        new_industry = await create_industry(db, industry_data.name, current_user)
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
            .filter(
                Industry.id == new_industry.id, Industry.user_id == current_user.id
            )
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
        logger.error(f"予期しないエラーが発生しました: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="予期しないエラーが発生しました。",
        )


@router.delete("/{industry_id}")
async def remove_industry(
    industry_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an industry and its categories from the database."""
    try:
        result = await delete_industry(db, industry_id, current_user)
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
            detail=f"予期しないエラーが発生しました: {str(e)}",
        )
