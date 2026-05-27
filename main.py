import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.database.engine import create_db, drop_db, session_maker
from app.handlers import base_hndlrs, category_hndlrs
from app.middlewares.db_middleware import DatabaseSessionUserMiddleware
from config.config import Config, load_config
from logger.logging import setup_logging

setup_logging()
logger = logging.getLogger("my_bot")


async def on_startup(bot: Bot):
    run_param = False
    if run_param:
        await drop_db()
        logger.info("Таблицы были удалены")

    await create_db()
    logger.info("Таблицы созданы")


async def main():
    try:
        logger.info("Бот запущен")
        config: Config = load_config()
        logger.info("Конфигурация загружена")

        bot = Bot(
            token=config.bot.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        # Инициализируем Redis
        redis = Redis(host="localhost", port=6380)

        # Инициализируем хранилище
        storage = RedisStorage(redis=redis)

        dp = Dispatcher(storage=storage)
        dp.startup.register(on_startup)
        dp.update.middleware(DatabaseSessionUserMiddleware(session_pool=session_maker))

        dp.include_router(base_hndlrs.router)
        dp.include_router(category_hndlrs.router)

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удалён, запускаем polling")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error("Ошибка при запуске бота s% - ", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
