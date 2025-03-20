
from datetime import datetime, timezone
from typing import List, Optional

from models.base import Base
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


def get_utc_now():
    """Return current UTC time with timezone info"""
    return datetime.now(timezone.utc)


class Review(Base):
    """
    Tracks metadata for an uploaded Excel file (whether 'past' or 'new').
    Could also track which stage (combined, cleaned, processed).
    """

    __tablename__ = "review"

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
        ForeignKey(
            "review.id", ondelete="CASCADE"
        ),
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

    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        onupdate=get_utc_now,
    )


class IndustryIndex(Base):
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
    index_path: Mapped[str] = mapped_column(String)
    cached_data_path: Mapped[str] = mapped_column(
        String
    )
    embeddings_model: Mapped[str] = mapped_column(
        String
    )
    reviews_included: Mapped[int] = mapped_column(
        Integer, default=0
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=get_utc_now,
        onupdate=get_utc_now,
    )

    industry: Mapped["Industry"] = relationship(back_populates="index")


class Industry(Base):
    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    categories: Mapped[List["Category"]] = relationship(
        back_populates="industry", cascade="all"
    )
    reviews: Mapped[List["Review"]] = relationship(
        back_populates="industry", cascade="all"
    )
    index: Mapped["IndustryIndex"] = relationship(
        back_populates="industry",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    industry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("industries.id", ondelete="CASCADE")
    )
    industry: Mapped["Industry"] = relationship(back_populates="categories")
