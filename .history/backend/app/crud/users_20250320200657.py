from app.models.users import User
from app.schemas.users import UserCreateModel
from app.users.utils import get_hashed_password
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


async def create_user(db: AsyncSession, user: UserCreateModel):
    try:
        user_data_dict = user.model_dump(exclude={"password"})
        new_user = User(**user_data_dict)
        new_user.hashed_password = get_hashed_password(user.password)
        db.add(new_user)
        await db.commit()
        return new_user
    except Exception as e:
        await db.rollback()
        raise e


async def get_user(db: AsyncSession, user_id: int):
    try:
        stmt = select(User).filter(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        return user
    except Exception as e:
        raise e


async def get_user_by_username(db: AsyncSession, username: str):
    try:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        user = result.scalars().first()
        return user
    except Exception as e:
        raise e


async def delete_user_by_id(db: AsyncSession, user_id: int):
    try:
        stmt = select(User).filter(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if user is None:
            return False
        await db.delete(user)
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise e
