import asyncio
import logging

from aiogram import Bot, Dispatcher

from config.config import Config, load_config
from handlers import user_handler

logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting bot...")
    print("Бот начал работу...")
    config: Config = load_config()
    bot = Bot(
        token=config.bot.token,
    )
    dp = Dispatcher()

    dp.include_router(user_handler.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
