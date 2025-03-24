from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.core.database import Base
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.industries import Industry


class Index(Base):
    """
    Tracks the state of FAISS index for each industry.
    """

    __tablename__ = "industry_indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    industry_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("industries.id", ondelete="CASCADE"),
        index=True,
        unique=True,
    )
    industry: Mapped["Industry"] = relationship(back_populates="index")
    index_path: Mapped[str] = mapped_column(String)
    cached_data_path: Mapped[str] = mapped_column(String)
    embeddings_model: Mapped[str] = mapped_column(String)
    reviews_included: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )


class IndexJob(Base):
    __tablename__ = "index_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    industry_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("industries.id", ondelete="CASCADE"),
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "pending", "processing", "completed", "failed"
    error: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )
    reviews_included = mapped_column(Integer, nullable=True)
    progress = mapped_column(Float, default=0)
