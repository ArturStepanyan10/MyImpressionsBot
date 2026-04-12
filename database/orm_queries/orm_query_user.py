from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models import User

async def orm_add_user(
    session: AsyncSession,
    name: str,
    last_name: str,
    telegram_id: int,
    username: str
):
    
    query = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(query)
    if result.first() is None:
        session.add(
            User(name=name, last_name=last_name, telegram_id=telegram_id, username=username)
        )
        await session.commit()
        