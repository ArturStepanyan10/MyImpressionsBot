import asyncio
import logging

from aiogram import Bot, Dispatcher

from config.config import Config, load_config

logger = logging.getLogger(__name__)


async def main():

    logger.info("Starting bot...")

    # Загружаем конфиг
    config: Config = load_config()

    # Инициализируем бот и диспетчер
    bot = Bot(
        token=config.bot.token,
    )
    dp = Dispatcher()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


asyncio.run(main())
