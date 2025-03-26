from typing import Annotated

from app.core.database import get_db
from app.crud.users import get_user_by_username
from app.models.users import User
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .security import TokenType, oauth2_scheme, verify_token


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    token_data = await verify_token(token, TokenType.ACCESS, db)
    if token_data is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await get_user_by_username(db=db, username=token_data.username)

    if user:
        return user

    raise HTTPException(status_code=401, detail="Invalid token")
