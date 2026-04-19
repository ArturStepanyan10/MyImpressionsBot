import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from database.models import User
from logger.logging import setup_logging

setup_logging()
logger = logging.getLogger("my_bot")


class DataBaseSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool: async_sessionmaker):
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session

            tg_user = data.get("event_from_user") or getattr(event, "from_user", None)

            if tg_user:
                search_user = await session.execute(
                    select(User).where(User.telegram_id == tg_user.id)
                )
                db_user = search_user.scalar_one_or_none()

                if db_user is None:
                    db_user = User(
                        name=tg_user.first_name,
                        last_name=tg_user.last_name or "",
                        telegram_id=tg_user.id,
                        username=tg_user.username or "",
                    )
                    session.add(db_user)
                    await session.flush()
                else:
                    db_user.name = tg_user.first_name
                    db_user.last_name = tg_user.last_name or ""
                    db_user.username = tg_user.username or ""

                data["db_user"] = db_user

            try:
                response = await handler(event, data)
                await session.commit()
                return response
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка в middleware: {e}")
                raise
