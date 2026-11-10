import logging

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.common_kb import common_btns
from app.lexicon.lexicon import LEXICON_RU
from app.services.error_service import ErrorService
from app.services.item_services import cancel_item_edit

router = Router()
logger = logging.getLogger("my_bot")
service = ErrorService
CANCEL_KEYBOARDS = {
    "all_category": all_category_keyboard,
}


@router.message(CommandStart())
async def process_start_command(message: Message, db_user: User, state: FSMContext):
    """Обрабатывает команду /start."""

    await state.clear()
    await message.answer(
        f"Приветствую тебя, дорогой {db_user.name}! 👋 \n\n{LEXICON_RU.get('/start')}",
        reply_markup=all_category_keyboard,
    )


@router.message(F.text == "/help")
async def process_help_command(message: Message, state: FSMContext):
    """Обрабатывает команду /help."""

    keyboard = (
        common_btns["cancel"]
        if await state.get_state() is not None
        else all_category_keyboard
    )
    await message.answer(LEXICON_RU.get("/help"), reply_markup=keyboard)


@router.message(StateFilter("*"), F.text == "Отменить")
async def process_cancel_command(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    """Обрабатывает отмену текущего действия и очищает состояние FSM.
    Действует для любого состояния.
    """

    data = await state.get_data()
    if data.get("cancel_keyboard") == "item_card":
        await cancel_item_edit(message, state, session, db_user.id)
        return

    # выбираем клавиатуру для ответа в зависимости от того, откуда была вызвана команда отмены
    keyboard_name = data.get("cancel_keyboard", "all_category")
    keyboard = CANCEL_KEYBOARDS.get(keyboard_name, all_category_keyboard)

    await state.clear()
    await message.answer(text="Действие отменено 😕", reply_markup=keyboard)


@router.errors()
async def process_global_error(event: ErrorEvent):
    """
    Обрабатывает все необработанные исключения.
    """
    exception = event.exception
    text = service.get_error_text(exception)

    logger.error(
        "Ошибка при обработке update_id=%s",
        event.update.update_id,
        exc_info=(type(exception), exception, exception.__traceback__),
    )

    if event.update.callback_query:
        await service.answer_callback(event.update.callback_query, text)

    message = service.get_message_from_error_event(event)
    if message:
        await service.send_error_message(message, text)

    return True
