import asyncio
import logging

from aiogram import Bot, Dispatcher

from config.config import Config, load_config
from database.engine import create_db, drop_db, session_maker
from handlers import user_handler
from logger.logging import setup_logging
from middlewares.db_middleware import DataBaseSessionMiddleware

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
        )
        dp = Dispatcher()
        dp.startup.register(on_startup)
        dp.update.middleware(DataBaseSessionMiddleware(session_pool=session_maker))

        dp.include_router(user_handler.router)

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удалён, запускаем polling")
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception("Ошибка при запуске бота s% - ", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
