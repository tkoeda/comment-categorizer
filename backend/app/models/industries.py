from typing import TYPE_CHECKING, List

from app.core.database import Base
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.index import Index
    from app.models.reviews import Review
    from app.models.users import User


class Industry(Base):
    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    user: Mapped["User"] = relationship(back_populates="industries")
    categories: Mapped[List["Category"]] = relationship(
        back_populates="industry", cascade="all"
    )
    reviews: Mapped[List["Review"]] = relationship(
        back_populates="industry", cascade="all"
    )
    index: Mapped["Index"] = relationship(
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
