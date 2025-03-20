from typing import Any

from app.auth.dependencies import get_current_user
from app.auth.security import oauth2_scheme
from app.core.database import get_db
from app.models.users import User
from auth.security import blacklist_token
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class OpenAIApiKeyUpdate(BaseModel):
    api_key: str = Field(..., description="Your OpenAI API key")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
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


@router.put("/me/openai-api-key", status_code=status.HTTP_200_OK)
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
        # Update the API key
        current_user.openai_api_key = api_key_update.api_key
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)

        return {
            "message": "OpenAI API key updated successfully",
            "has_api_key": current_user.encrypted_openai_api_key is not None,
        }
    except ValueError as e:
        # Handle encryption errors (like missing FERNET_KEY)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to encrypt API key: {str(e)}",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating API key: {str(e)}",
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
