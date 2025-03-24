import logging
from typing import Any, Literal

import bcrypt
from app.models.users import User
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

logger = logging.getLogger(__name__)


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


async def verify_openai_api_key(api_key: str) -> tuple[bool, str]:
    """
    Verify that an OpenAI API key is valid by making a lightweight API call.

    Args:
        api_key: The OpenAI API key to verify

    Returns:
        tuple: (is_valid, error_message)
            - is_valid: Boolean indicating if the key is valid
            - error_message: String with error details if invalid, empty string if valid
    """
    if not api_key:
        return False, "API key cannot be empty"

    try:
        client = AsyncOpenAI(api_key=api_key)
        # Making a lightweight API call to verify
        await client.models.list()
        return True, ""
    except Exception as e:
        error_msg = str(e)
        logger.warning(f"Invalid OpenAI API key: {error_msg}")

        # Provide a user-friendly message based on common errors
        if "Incorrect API key" in error_msg or "invalid_api_key" in error_msg:
            return False, "Invalid API key format or credentials"
        elif "rate_limit" in error_msg:
            return False, "API key rate limited, please try again later"
        else:
            return False, f"API key validation failed: {error_msg}"
