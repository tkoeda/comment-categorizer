from typing import Any, Literal

import bcrypt
from app.models.users import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select


def get_hashed_password(password: str) -> str:
    hashed_password: str = bcrypt.hashpw(
        password.encode(), bcrypt.gensalt()
    ).decode()
    return hashed_password


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    correct_password: bool = bcrypt.checkpw(
        plain_password.encode(), hashed_password.encode()
    )
    return correct_password


async def authenticate_user(
    username: str, password: str, db: AsyncSession
) -> dict[str, Any] | Literal[False]:
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return False

    elif not await verify_password(password, user.hashed_password):
        return False

    return user
