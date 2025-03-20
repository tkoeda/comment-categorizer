from app.models.industries import Category, Industry
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload


async def create_industry(db: AsyncSession, name: str, user_id: int):
    """Create a new industry."""
    stmt = select(Industry).filter(
        Industry.name == name, Industry.user_id == user_id
    )
    result = await db.execute(stmt)
    existing_industry = result.scalar_one_or_none()
    if existing_industry:
        return None

    industry = Industry(name=name, user_id=user_id)
    db.add(industry)
    await db.commit()
    await db.refresh(industry)
    return industry


async def get_industry(db: AsyncSession, industry_id: int):
    """Retrieve an industry by its ID."""
    stmt = (
        select(Industry)
        .filter(Industry.id == industry_id)
        .options(selectinload(Industry.categories))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_industry(db: AsyncSession, industry_id: int):
    """Delete an industry by ID."""
    industry = await get_industry(db, industry_id)
    if not industry:
        return False

    try:
        await db.delete(industry)
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Error deleting industry: {str(e)}"
        )


async def get_industries(db: AsyncSession):
    """Retrieve all industries with their categories."""
    stmt = select(Industry).options(selectinload(Industry.categories))
    result = await db.execute(stmt)
    industries = result.scalars().all()
    return [
        {
            "id": industry.id,
            "name": industry.name,
            "categories": [category.name for category in industry.categories],
        }
        for industry in industries
    ]


async def create_category(db: AsyncSession, name: str, industry_id: int):
    """Create a new category under an industry."""
    category = Category(name=name, industry_id=industry_id)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category
