from app.models.industries import Category, Industry
from app.models.users import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload


async def create_industry(db: AsyncSession, name: str, user: User):
    """Create a new industry."""
    try:
        stmt = select(Industry).filter(
            Industry.name == name, Industry.user_id == user.id
        )
        result = await db.execute(stmt)
        existing_industry = result.scalar_one_or_none()
        if existing_industry:
            return None

        industry = Industry(name=name, user_id=user.id)
        db.add(industry)
        await db.commit()
        await db.refresh(industry)
        return industry
    except Exception:
        await db.rollback()
        raise


async def get_industry(db: AsyncSession, industry_id: int, user: User):
    """Retrieve an industry by its ID."""
    stmt = (
        select(Industry)
        .filter(Industry.id == industry_id, Industry.user_id == user.id)
        .options(selectinload(Industry.categories))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def delete_industry(db: AsyncSession, industry_id: int, user: User):
    """Delete an industry by ID."""
    try:
        industry = await get_industry(db, industry_id, user)
        if not industry:
            return False

        await db.delete(industry)
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        raise


async def get_industries(db: AsyncSession, user: User):
    """Retrieve all industries with their categories."""
    stmt = (
        select(Industry)
        .filter(Industry.user_id == user.id)
        .options(selectinload(Industry.categories))
    )
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
    try:
        category = Category(name=name, industry_id=industry_id)
        db.add(category)
        await db.commit()
        await db.refresh(category)
        return category
    except Exception:
        await db.rollback()
        raise
