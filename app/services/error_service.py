import asyncio
import logging

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import CallbackQuery, ErrorEvent, Message

from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.lexicon.lexicon import ERROR_LEXICON_RU

logger = logging.getLogger("my_bot")


class ErrorService:
    """Сервис для обработки ошибок и ответов пользователю при сбоях."""

    @staticmethod
    def get_message_from_error_event(event: ErrorEvent) -> Message | None:
        """Достаёт сообщение из события ошибки, если по нему можно ответить пользователю."""

        update = event.update

        if update.message:
            return update.message
        if update.edited_message:
            return update.edited_message

        callback = update.callback_query
        if callback and isinstance(callback.message, Message):
            return callback.message

        return None

    @staticmethod
    def get_error_text(exception: Exception) -> str:
        """Подбирает пользовательский текст ответа по типу возникшей ошибки."""

        if isinstance(exception, TelegramRetryAfter):
            return ERROR_LEXICON_RU["retry_after_error"].format(
                seconds=exception.retry_after
            )

        if isinstance(
            exception,
            (
                asyncio.TimeoutError,
                TimeoutError,
                TelegramNetworkError,
                TelegramServerError,
            ),
        ):
            return ERROR_LEXICON_RU["timeout_error"]

        return ERROR_LEXICON_RU["default_error"]

    @staticmethod
    async def answer_callback(callback: CallbackQuery, text: str) -> None:
        """Показывает пользователю alert, если ошибка произошла при нажатии кнопки."""

        try:
            await callback.answer(text=text, show_alert=True)
        except TelegramAPIError:
            logger.warning("Не удалось ответить на callback после ошибки", exc_info=True)

    @staticmethod
    async def send_error_message(message: Message, text: str) -> None:
        """Отправляет сообщение об ошибке в чат пользователя."""

        try:
            await message.answer(text=text, reply_markup=all_category_keyboard)
        except TelegramAPIError:
            logger.warning("Не удалось отправить сообщение об ошибке", exc_info=True)
