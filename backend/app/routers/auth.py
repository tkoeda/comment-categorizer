import logging
from datetime import timedelta
from typing import Annotated, Union

from app.core.config import settings
from app.core.database import get_db
from app.utils.routers.users import authenticate_user
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import (
    TokenType,
    blacklist_tokens,
    create_access_token,
    create_refresh_token,
    oauth2_scheme,
    verify_token,
)
from ..schemas.auth import Token

logging.basicConfig(level=logging.WARNING)

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    user = await authenticate_user(
        username=form_data.username, password=form_data.password, db=db
    )
    if not user:
        print("user", user)
        raise HTTPException(
            status_code=401, detail="Wrong username, email or password."
        )

    access_token = await create_access_token(data={"sub": user.username})

    refresh_token = await create_refresh_token(data={"sub": user.username})
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=max_age,
        path="/",
    )

    return {"access_token": access_token}


@router.post("/refresh")
async def refresh_access_token(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing.")

    user_data = await verify_token(refresh_token, TokenType.REFRESH, db)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    new_access_token = await create_access_token(data={"sub": user_data.username})
    return {"access_token": new_access_token}


@router.post("/logout")
async def logout(
    response: Response,
    access_token: str = Depends(oauth2_scheme),
    refresh_token: Union[str, None] = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Refresh token missing.")
        await blacklist_tokens(
            access_token=access_token, refresh_token=refresh_token, db=db
        )
        response.delete_cookie(key="refresh_token", path="/")

        return {"message": "Logged out successfully"}

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")
