from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IndexStatusResponse(BaseModel):
    exists: bool
    count: int
    lastUpdated: Optional[datetime] = None


class UpdatePastReviewsIndexRequest(BaseModel):
    industry_id: int
    past_cleaned_id: int
    mode: str
