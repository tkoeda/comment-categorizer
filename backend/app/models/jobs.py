from datetime import datetime, timezone
from typing import Optional

from app.core.database import Base
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ReviewJob(Base):
    __tablename__ = "review_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    industry_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("industries.id", ondelete="CASCADE"),
    )

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    # Foreign key to the new cleaned review
    new_cleaned_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False
    )

    # Reference to the final output review (will be set when job completes)
    final_review_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("reviews.id", ondelete="SET NULL"), nullable=True
    )

    # Job configuration
    use_past_reviews: Mapped[bool] = mapped_column(default=True)
    # Job status tracking
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )  # "pending", "processing", "completed", "failed", "cancelled"

    progress: Mapped[float] = mapped_column(Float, default=0)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Statistics about the job
    reviews_processed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_reviews: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="review_jobs")
    industry = relationship("Industry")
    new_cleaned_review = relationship("Review", foreign_keys=[new_cleaned_id])
    final_review = relationship("Review", foreign_keys=[final_review_id])
