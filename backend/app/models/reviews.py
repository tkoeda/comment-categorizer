import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from app.core.database import Base
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.industries import Industry
    from app.models.users import User


class Review(Base):
    """
    Tracks metadata for an uploaded Excel file (whether 'past' or 'new').
    Could also track which stage (combined, cleaned, processed).
    """

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    display_name: Mapped[str] = mapped_column(String, index=True)
    industry_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("industries.id", ondelete="CASCADE"),
        index=True,
    )
    industry: Mapped["Industry"] = relationship(back_populates="reviews")
    review_type: Mapped[str] = mapped_column(String, index=True)
    stage: Mapped[str] = mapped_column(String, index=True)

    file_path: Mapped[str] = mapped_column(String)

    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    children: Mapped[List["Review"]] = relationship(
        "Review",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
        uselist=True,
    )
    parent: Mapped[Optional["Review"]] = relationship(
        "Review",
        back_populates="children",
        remote_side=[id],
        foreign_keys=[parent_id],
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    user: Mapped["User"] = relationship(back_populates="reviews")
