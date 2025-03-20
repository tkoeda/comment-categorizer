from datetime import datetime

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str


class TokenData(BaseModel):
    username: str


class TokenBlacklistBase(BaseModel):
    token: str
    expires_at: datetime


class TokenBlacklistCreate(TokenBlacklistBase):
    pass


class TokenBlacklistUpdate(TokenBlacklistBase):
    pass
