from datetime import datetime
from typing import Dict, List, Optional, Union

from fastapi import UploadFile
from pydantic import BaseModel


class FileItem(BaseModel):
    id: int
    display_name: Union[str, None] = None
    file_path: str
    stage: str
    review_type: str
    created_at: str


class FileListResponse(BaseModel):
    new: Dict[str, List[FileItem]]
    past: Dict[str, List[FileItem]]
    final: List[FileItem]


class CombineAndCleanRequest(BaseModel):
    industry_id: int
    review_type: str
    display_name: Optional[str] = None
    files: List[UploadFile]


class CombineAndCleanResponse(BaseModel):
    message: str
    combined_file: str
    cleaned_file: str
    combined_review_id: int
    cleaned_review_id: int


class IndexStatusResponse(BaseModel):
    exists: bool
    count: int
    lastUpdated: Union[datetime, None] = None


class ProcessReviewsSavedRequest(BaseModel):
    industry_id: int
    use_past_reviews: bool
    new_cleaned_id: int
    display_name: Union[str, None] = None


class DownloadFileResponse(BaseModel):
    file_path: str
    display_name: str
    media_type: str
