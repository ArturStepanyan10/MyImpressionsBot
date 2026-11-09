from html import escape

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CategoryAction
from app.database.models import Category, User
from app.database.orm_queries.orm_query_category import orm_get_all_categories
from app.database.orm_queries.orm_query_item import ORMQueryItem
from app.handlers.item_action_hndlrs import router as item_action_router
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.category_kb.inline_kb import (
    add_category_inline_keyboard,
    get_category_inline_keyboard,
)
from app.keyboards.common_kb import common_btns
from app.keyboards.item_kb.callbacks import (
    ITEM_STATUS_FILTERS,
    ItemDetailsCallback,
    ItemListCallback,
)
from app.keyboards.item_kb.inline_kb import (
    get_item_created_keyboard,
    get_item_details_keyboard,
)
from app.lexicon.lexicon import CATEGORY_LEXICON_RU, ITEM_LEXICON_RU
from app.services.category_services import CategoryService
from app.services.item_services import (
    clear_item_form,
    get_callback_item,
    is_http_url,
    send_category_items,
    send_item_card,
)
from app.states.forms_state import FSMFillFormItemState

router = Router()
router.include_router(item_action_router)


async def _get_owned_category_from_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    user_id: int,
) -> tuple[int, Category] | None:
    """Извлекает ID из callback и проверяет доступ пользователя к категории."""

    category_id = int(callback.data.rsplit("_", maxsplit=1)[-1])
    category = await CategoryService.get_owned_category(
        callback=callback,
        category_id=category_id,
        db_user_id=user_id,
        session=session,
    )
    if category is None:
        return None

    return category_id, category


@router.callback_query(F.data.startswith("list_category_"))
async def process_category_items(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    """Показывает список элементов выбранной категории пользователя."""

    category_data = await _get_owned_category_from_callback(
        callback,
        session,
        db_user.id,
    )
    if category_data is None:
        return
    _, category = category_data
    await clear_item_form(callback.message, state)
    await callback.answer()
    await send_category_items(callback.message, session, category, db_user.id)


@router.callback_query(ItemListCallback.filter())
async def process_filtered_category_items(
    callback: CallbackQuery,
    callback_data: ItemListCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    """Фильтрация и возврат из карточки к прежнему списку."""

    if callback_data.status not in ITEM_STATUS_FILTERS:
        await callback.answer(ITEM_LEXICON_RU["invalid_filter"], show_alert=True)
        return

    category = await CategoryService.get_owned_category(
        callback, callback_data.category_id, db_user.id, session
    )
    if category is None:
        return

    await clear_item_form(callback.message, state)
    await callback.answer()
    await send_category_items(
        callback.message,
        session,
        category,
        db_user.id,
        callback_data.status,
        callback_data.page,
    )


@router.callback_query(ItemDetailsCallback.filter())
async def process_item_details(
    callback: CallbackQuery,
    callback_data: ItemDetailsCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    """Открывает карточку только из категории текущего пользователя."""

    item = await get_callback_item(callback, callback_data, session, db_user.id)
    if item is None:
        return

    await clear_item_form(callback.message, state)
    await callback.answer()
    await send_item_card(
        callback.message,
        item,
        get_item_details_keyboard(
            item.category_id, item.id, callback_data.status, callback_data.page
        ),
    )


@router.callback_query(F.data == "item_categories")
async def process_back_to_categories(
    callback: CallbackQuery, session: AsyncSession, db_user: User, state: FSMContext
) -> None:
    """Возвращает из списка элементов к категориям пользователя."""

    categories = await orm_get_all_categories(session, user_id=db_user.id)
    await clear_item_form(callback.message, state)
    await callback.answer()
    await callback.message.answer(
        CATEGORY_LEXICON_RU["list_marker" if categories else "list_empty"],
        reply_markup=(
            get_category_inline_keyboard(categories, CategoryAction.LIST.value)
            if categories
            else add_category_inline_keyboard
        ),
    )


@router.callback_query(F.data.startswith("add_item_"))
async def process_add_item(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    db_user: User,
) -> None:
    """Запускает форму добавления элемента в выбранную категорию."""

    category_data = await _get_owned_category_from_callback(
        callback,
        session,
        db_user.id,
    )
    if category_data is None:
        return
    category_id, _ = category_data

    await state.set_data(
        {
            "category_id": category_id,
            "cancel_keyboard": "all_category",
        }
    )
    await state.set_state(FSMFillFormItemState.fill_title)

    await callback.answer()
    await callback.message.answer(
        ITEM_LEXICON_RU["add_title_prompt"],
        reply_markup=common_btns["cancel"],
    )


@router.message(StateFilter(FSMFillFormItemState.fill_title))
async def process_item_title(message: Message, state: FSMContext) -> None:
    """Сохраняет название добавляемого элемента."""

    title = message.text.strip() if message.text else ""
    if not 1 <= len(title) <= 255:
        await message.answer(ITEM_LEXICON_RU["invalid_title"])
        return

    await state.update_data(title=title)
    await state.set_state(FSMFillFormItemState.fill_review)
    await message.answer(ITEM_LEXICON_RU["add_review_prompt"])


@router.message(StateFilter(FSMFillFormItemState.fill_review))
async def process_item_review(message: Message, state: FSMContext) -> None:
    """Сохраняет отзыв о добавляемом элементе."""

    review = message.text.strip() if message.text else ""
    if not review:
        await message.answer(ITEM_LEXICON_RU["invalid_review"])
        return

    await state.update_data(review=review)
    await state.set_state(FSMFillFormItemState.fill_rating)
    await message.answer(ITEM_LEXICON_RU["add_rating_prompt"])


@router.message(StateFilter(FSMFillFormItemState.fill_rating))
async def process_item_rating(message: Message, state: FSMContext) -> None:
    """Проверяет и сохраняет оценку добавляемого элемента."""

    rating_text = message.text.strip() if message.text else ""
    if not rating_text.isdigit():
        await message.answer(ITEM_LEXICON_RU["invalid_rating"])
        return

    rating = int(rating_text)
    if not 1 <= rating <= 5:
        await message.answer(ITEM_LEXICON_RU["invalid_rating"])
        return

    await state.update_data(rating=rating)
    await state.set_state(FSMFillFormItemState.fill_image_url)
    await message.answer(ITEM_LEXICON_RU["add_image_url_prompt"])


@router.message(StateFilter(FSMFillFormItemState.fill_image_url))
async def process_item_image_url(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    db_user: User,
) -> None:
    """Проверяет ссылку и сохраняет новый элемент в базе данных."""

    image_url = message.text.strip() if message.text else ""
    if not is_http_url(image_url):
        await message.answer(ITEM_LEXICON_RU["invalid_image_url"])
        return

    data = await state.get_data()
    required_fields = {"category_id", "title", "review", "rating"}
    if not required_fields.issubset(data):
        await state.clear()
        await message.answer(
            ITEM_LEXICON_RU["form_expired"],
            reply_markup=all_category_keyboard,
        )
        return

    category_id = data["category_id"]
    item_queries = ORMQueryItem(
        session=session,
        category_id=category_id,
        user_id=db_user.id,
    )
    item = await item_queries.add_item(
        {
            "title": data["title"],
            "review": data["review"],
            "rating": data["rating"],
            "image_url": image_url,
        }
    )

    await state.clear()

    if item is None:
        await message.answer(
            ITEM_LEXICON_RU["category_unavailable"],
            reply_markup=all_category_keyboard,
        )
        return

    await message.answer(
        ITEM_LEXICON_RU["add_success"].format(
            title=escape(item.title),
            rating=item.rating,
            status=escape(item.status.value),
        ),
        reply_markup=all_category_keyboard,
    )
    await message.answer(
        ITEM_LEXICON_RU["after_add_actions"],
        reply_markup=get_item_created_keyboard(category_id),
    )
