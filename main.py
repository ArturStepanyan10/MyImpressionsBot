import asyncio
import logging

from aiogram import Bot, Dispatcher

from config.config import Config, load_config
from handlers import user_handler
from logger.logging import setup_logging

setup_logging()
logger = logging.getLogger("my_bot")


async def main():
    try:
        logger.info("Бот запущен")
        config: Config = load_config()
        logger.info("Конфигурация загружена")

        bot = Bot(
            token=config.bot.token,
        )
        dp = Dispatcher()

        dp.include_router(user_handler.router)

        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook удалён, запускаем polling")
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception("Ошибка при запуске бота s% - ", e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
