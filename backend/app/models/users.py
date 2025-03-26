import os
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Union

from app.core.database import Base
from cryptography.fernet import Fernet
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.index import Index, IndexJob
    from app.models.industries import Industry
    from app.models.reviews import Review


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        index=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    encrypted_openai_api_key: Mapped[Union[str, None]] = mapped_column(
        String, nullable=True
    )
    reviews: Mapped[List["Review"]] = relationship(
        "Review", back_populates="user", cascade="all, delete-orphan"
    )
    industries: Mapped[List["Industry"]] = relationship(
        "Industry", back_populates="user", cascade="all, delete-orphan"
    )
    indexes: Mapped[List["Index"]] = relationship(
        "Index", back_populates="user", cascade="all, delete-orphan"
    )
    index_jobs: Mapped[List["IndexJob"]] = relationship(
        "IndexJob", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def openai_api_key(self) -> Union[str, None]:
        """Decrypt and return the OpenAI API key"""
        if not self.encrypted_openai_api_key:
            return None
        return self._decrypt_api_key(self.encrypted_openai_api_key)

    @openai_api_key.setter
    def openai_api_key(self, plain_api_key: Union[str, None]) -> None:
        """Encrypt and store the OpenAI API key"""
        if plain_api_key is None:
            self.encrypted_openai_api_key = None
        else:
            self.encrypted_openai_api_key = self._encrypt_api_key(plain_api_key)

    @staticmethod
    def _get_fernet_key():
        """Get the Fernet key from environment variables or create one"""
        key = os.environ.get("FERNET_KEY")
        if not key:
            # In production, you should handle this case properly
            # This is just a fallback for development
            raise ValueError("FERNET_KEY environment variable is not set")
        return key

    @classmethod
    def _encrypt_api_key(cls, api_key: str) -> str:
        """Encrypt the API key"""
        f = Fernet(cls._get_fernet_key())
        return f.encrypt(api_key.encode()).decode()

    @classmethod
    def _decrypt_api_key(cls, encrypted_api_key: str) -> str:
        """Decrypt the API key"""
        f = Fernet(cls._get_fernet_key())
        return f.decrypt(encrypted_api_key.encode()).decode()
