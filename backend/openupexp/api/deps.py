from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from openupexp.db.session import sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
