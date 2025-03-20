from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from .models import TokenBlacklist
from .schemas import TokenBlacklistCreate


async def token_blacklist_create(
    db: AsyncSession, token: str, expires_at: datetime
) -> TokenBlacklistCreate:
    token_blacklist = TokenBlacklist(token=token, expires_at=expires_at)
    db.add(token_blacklist)
    await db.commit()
    await db.refresh(token_blacklist)
    return token_blacklist
