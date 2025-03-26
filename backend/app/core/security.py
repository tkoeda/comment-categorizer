from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from app.core.config import settings
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.auth import TokenData
from ..utils.routers.auth import token_blacklist_create, token_blacklist_exists

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


async def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC).replace(tzinfo=None) + expires_delta
    else:
        expire = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "token_type": TokenType.ACCESS})
    encoded_jwt: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def create_refresh_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC).replace(tzinfo=None) + expires_delta
    else:
        expire = datetime.now(UTC).replace(tzinfo=None) + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
    to_encode.update({"exp": expire, "token_type": TokenType.REFRESH})
    encoded_jwt: str = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def verify_token(
    token: str, expected_token_type: TokenType, db: AsyncSession
) -> TokenData | None:
    """Verify a JWT token and return TokenData if valid.

    Parameters
    ----------
    token: str
        The JWT token to be verified.
    expected_token_type: TokenType
        The expected type of token (access or refresh)
    db: AsyncSession
        Database session for performing database operations.

    Returns
    -------
    TokenData | None
        TokenData instance if the token is valid, None otherwise.
    """
    is_blacklisted = await token_blacklist_exists(db, token=token)
    if is_blacklisted:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("token_type")

        if username is None or token_type != expected_token_type:
            return None

        return TokenData(username=username)

    except JWTError:
        return None


async def blacklist_tokens(
    access_token: str, refresh_token: str, db: AsyncSession
) -> None:
    """Blacklist both access and refresh tokens.

    Parameters
    ----------
    access_token: str
        The access token to blacklist
    refresh_token: str
        The refresh token to blacklist
    db: AsyncSession
        Database session for performing database operations.
    """
    for token in [access_token, refresh_token]:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        expires_at = datetime.fromtimestamp(payload.get("exp"))
        await token_blacklist_create(db, token=token, expires_at=expires_at)


async def blacklist_token(token: str, db: AsyncSession) -> None:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    expires_at = datetime.fromtimestamp(payload.get("exp"))
    await token_blacklist_create(db, token=token, expires_at=expires_at)
