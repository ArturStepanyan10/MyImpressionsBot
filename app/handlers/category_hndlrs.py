import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CategoryAction
from app.database.models import User
from app.database.orm_queries.orm_query_category import (
    orm_delete_category,
    orm_get_all_categories,
)
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.category_kb.inline_kb import (
    add_category_inline_keyboard,
    get_category_inline_keyboard,
)
from app.keyboards.common_kb import common_btns
from app.lexicon.lexicon import CATEGORY_LEXICON_RU
from app.services.category_services import CategoryService
from app.states.forms_state import FSMFillFormCategoryState

router = Router()
TITLE_PATTERN = re.compile(r"^[\w\s\-]{1,50}$", re.UNICODE)
service = CategoryService


@router.message(F.text == "Ваши категории")
async def process_list_category(message: Message, session: AsyncSession):
    """
    Обрабатывает запрос на просмотр всех категорий и выводит их в виде инлайн клавиатуры.
    Если категорий нет, предлагает создать новую.
    """

    categories = await orm_get_all_categories(session)
    if categories:
        await message.answer(
            text=CATEGORY_LEXICON_RU["list_marker"],
            reply_markup=get_category_inline_keyboard(
                categories,
                CategoryAction.LIST.value,
            ),
        )
    else:
        await message.answer(
            text=CATEGORY_LEXICON_RU["list_empty"],
            reply_markup=add_category_inline_keyboard,
        )


@router.message(F.text == "Добавить категорию")
async def process_fill_title_category(message: Message, state: FSMContext):
    """
    Обрабатывает команду 'Добавить категорию'
    и переводит бота в состояние ожидания ввода названия категории.
    """

    await service.start_process_add_category(message, state)


@router.message(
    StateFilter(FSMFillFormCategoryState.fill_add_title),
    F.text.func(lambda text: bool(text and TITLE_PATTERN.fullmatch(text.strip()))),
)
async def process_title_sent(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
):
    """
    Обрабатывает введенное название категории, сохраняет его в состоянии FSM
    и добавляет новую категорию в базу данных.
    """

    # Сохраняем введенное название имя в хранилище по ключу "title"
    title = message.text.strip()

    category = await service.get_category_by_title(title, session)
    if category:
        await message.answer(
            text=CATEGORY_LEXICON_RU["add_duplicate"],
            reply_markup=common_btns["cancel"],
        )
        return

    await state.update_data(title=title)

    # Получаем данные из хранилища
    state_data = await state.get_data()

    # Обращаемся к сервису для создания категории, передавая данные и сессию базы данных
    try:
        await service.create_category(
            data={"title": state_data.get("title"), "user_id": db_user.id},
            session=session,
        )
    except IntegrityError:
        await session.rollback()
        await message.answer(
            text=CATEGORY_LEXICON_RU["add_duplicate"],
            reply_markup=common_btns["cancel"],
        )
        return

    # Выходит из состояния (Диалог закончен)
    await state.clear()
    await message.answer(
        text=CATEGORY_LEXICON_RU["add_success"],
        reply_markup=all_category_keyboard,
    )


@router.message(StateFilter(FSMFillFormCategoryState.fill_add_title))
async def warning_not_title(message: Message):
    """
    Сработывает, если введенное название категории не соответствует шаблону
    и просит ввести корректное название.
    """

    await message.answer(text=CATEGORY_LEXICON_RU["invalid_title"])


@router.callback_query(F.data == "add_category")
async def process_add_category_inline(callback: CallbackQuery, state: FSMContext):
    """
    Срабатывает на инлайн кнопку 'Добавить категорию' и
    переводит бота в состояние ожидания ввода названия категории.
    """

    await service.start_process_add_category(callback.message, state)


@router.message(F.text.in_(["Изменить категорию", "Удалить категорию"]))
async def process_update_category(message: Message, session: AsyncSession):
    """
    Обрабатывает команды 'Изменить категорию' и 'Удалить категорию',
    выводя список категорий в виде инлайн клавиатуры для выбора действия.
    """

    action = (
        CategoryAction.UPDATE.value
        if message.text.startswith("Изменить")
        else CategoryAction.DELETE.value
    )

    categories = await orm_get_all_categories(session)
    if not categories:
        await message.answer(CATEGORY_LEXICON_RU["category_empty"])
        return
    print(action)
    await message.answer(
        text=CATEGORY_LEXICON_RU["choose_category"],
        reply_markup=get_category_inline_keyboard(categories, action),
    )


@router.callback_query(F.data.startswith("update_category_"))
async def process_update_category_selection(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext, db_user: User
):
    """
    Срабатывает на инлайн кнопку выбора категории и
    переводит бота в состояние ожидания ввода нового названия.

    Также сохраняет ID выбранной категории в состоянии FSM для дальнейшего использования при обновлении.
    """

    category_id = int(callback.data.split("_")[-1])

    category = await service.validate_update_and_delete_process(
        callback, category_id, db_user.id, session
    )
    if not category:
        return

    await state.update_data(cancel_keyboard="all_category")

    # Сохраняем ID категории в состоянии для дальнейшего использования при обновлении
    await state.update_data(category_id=category_id)

    await callback.answer()
    # Устанавливаем состояние ожидания ввода нового названия
    await state.set_state(FSMFillFormCategoryState.fill_update_title)
    await callback.message.answer(
        CATEGORY_LEXICON_RU["update_title_prompt"].format(title=category.title),
        reply_markup=common_btns["cancel"],
    )


@router.message(
    StateFilter(FSMFillFormCategoryState.fill_update_title),
    F.text.func(lambda text: bool(text and TITLE_PATTERN.fullmatch(text.strip()))),
)
async def process_update_category_title(
    message: Message, session: AsyncSession, state: FSMContext, db_user: User
):
    """
    Обрабатывает введенное новое название категории,
    сохраняет его в состоянии FSM и обновляет категорию в базе данных.
    """

    new_title = message.text.strip()

    # Чтобы получить ID категории, который был сохранён при выборе категории для обновления
    data = await state.get_data()

    # Проверяем, существует ли категория с таким же названием
    # И если существует, то не разрешаем обновление
    category = await service.get_category_by_title(new_title, session)
    if category and category.id != data["category_id"]:
        await message.answer(
            text=CATEGORY_LEXICON_RU["update_duplicate"],
            reply_markup=common_btns["cancel"],
        )
        return

    upd_data = {
        "title": new_title,
        "user_id": db_user.id,
    }

    try:
        await service.update_category(data["category_id"], upd_data, session)
    except IntegrityError:
        await session.rollback()
        await message.answer(
            text=CATEGORY_LEXICON_RU["update_duplicate"],
            reply_markup=common_btns["cancel"],
        )
        return

    await message.answer(
        CATEGORY_LEXICON_RU["update_success"],
        reply_markup=all_category_keyboard,
    )
    await state.clear()


@router.callback_query(F.data.startswith("delete_category_"))
async def process_delete_category(
    callback: CallbackQuery, session: AsyncSession, db_user: User
):
    """Срабатывает на инлайн кнопку удаления категории, удаляет категорию из базы данных и уведомляет пользователя."""
    category_id = int(callback.data.split("_")[-1])

    category = await service.validate_update_and_delete_process(
        callback, category_id, db_user.id, session
    )
    if not category:
        return

    await orm_delete_category(session, category_id)

    await callback.message.answer(
        CATEGORY_LEXICON_RU["delete_success"].format(title=category.title),
        reply_markup=all_category_keyboard,
    )
