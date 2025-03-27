from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


# Pydantic models for request/response
class ReviewJobCreate(BaseModel):
    industry_id: int
    new_cleaned_id: int
    use_past_reviews: bool = False


class ReviewJobResponse(BaseModel):
    id: int
    industry_id: int
    user_id: UUID
    new_cleaned_id: int
    final_review_id: Optional[int] = None
    status: str
    progress: float
    reviews_processed: Optional[int] = None
    total_reviews: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ReviewJobList(BaseModel):
    jobs: List[ReviewJobResponse]
