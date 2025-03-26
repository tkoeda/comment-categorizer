from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ...models.auth import TokenBlacklist
from ...schemas.auth import TokenBlacklistCreate


async def token_blacklist_create(
    db: AsyncSession, token: str, expires_at: datetime
) -> TokenBlacklistCreate:
    token_blacklist = TokenBlacklist(token=token, expires_at=expires_at)
    db.add(token_blacklist)
    await db.commit()
    await db.refresh(token_blacklist)
    return token_blacklist


async def token_blacklist_exists(db: AsyncSession, token: str) -> bool:
    stmt = select(TokenBlacklist).filter(TokenBlacklist.token == token)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
