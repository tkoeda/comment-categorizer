from typing import Any

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import blacklist_token, oauth2_scheme
from app.crud.users import create_user
from app.models.users import User
from app.schemas.users import UserCreateModel
from app.utils.routers.users import verify_openai_api_key
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

router = APIRouter()


class OpenAIApiKeyUpdate(BaseModel):
    api_key: str = Field(..., description="Your OpenAI API key")


@router.post("/register")
async def register_user(
    user: UserCreateModel,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a new user.
    """
    try:
        query = select(User).where(User.username == user.username)
        result = await db.execute(query)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{user.username}' is already taken. Please choose a different username.",
            )
        new_user = await create_user(db, user)
        user_dict = {
            "id": new_user.id,
            "username": new_user.username,
        }
        return {
            "message": "User created successfully",
            "user": user_dict,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{str(e)}",
        )


@router.delete("/me")
async def delete_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> None:
    """
    Delete the currently authenticated user.
    This will delete all user data, including reviews and other associated records.
    This action cannot be undone.
    """
    try:
        # Delete the user
        await db.delete(current_user)
        await blacklist_token(token, db)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting user: {str(e)}",
        )


@router.put("/me/openai-api-key")
async def update_openai_api_key(
    api_key_update: OpenAIApiKeyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Update the user's OpenAI API key.
    The API key is encrypted before being stored in the database.
    """
    try:
        if not api_key_update.api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key cannot be empty",
            )

        is_valid, error_msg = await verify_openai_api_key(api_key_update.api_key)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OpenAI API key: {error_msg}",
            )

        # Update the API key
        current_user.openai_api_key = api_key_update.api_key
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
        return {
            "message": "OpenAI API key updated successfully",
            "has_api_key": current_user.encrypted_openai_api_key is not None,
        }
    except HTTPException:
        await db.rollback()
        raise
    except ValueError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid API key format: {str(e)}",
        )
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key. Please try again later.",
        )


@router.delete("/me/openai-api-key", status_code=status.HTTP_200_OK)
async def delete_openai_api_key(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Remove the user's OpenAI API key from the system.
    """
    try:
        current_user.openai_api_key = None
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)

        return {"message": "OpenAI API key removed successfully"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while removing API key: {str(e)}",
        )
