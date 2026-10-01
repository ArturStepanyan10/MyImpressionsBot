from html import escape
from urllib.parse import urlparse

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Category, User
from app.database.orm_queries.orm_query_item import ORMQueryItem
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.common_kb import common_btns
from app.keyboards.item_kb.inline_kb import (
    get_item_actions_keyboard,
    get_item_created_keyboard,
)
from app.lexicon.lexicon import ITEM_LEXICON_RU
from app.services.category_services import CategoryService
from app.states.forms_state import FSMFillFormItemState

router = Router()


def _is_http_url(value: str) -> bool:
    parsed_url = urlparse(value)
    return parsed_url.scheme in {"http", "https"} and bool(parsed_url.netloc)


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
) -> None:
    """Показывает список элементов выбранной категории пользователя."""

    category_data = await _get_owned_category_from_callback(
        callback,
        session,
        db_user.id,
    )
    if category_data is None:
        return
    category_id, category = category_data

    item_queries = ORMQueryItem(
        session=session,
        category_id=category_id,
        user_id=db_user.id,
    )
    items = await item_queries.get_all_items()

    await callback.answer()

    category_title = escape(category.title)
    if not items:
        await callback.message.answer(
            ITEM_LEXICON_RU["list_empty"].format(category=category_title),
            reply_markup=get_item_actions_keyboard(category_id),
        )
        return

    item_lines = []
    for number, item in enumerate(items, start=1):
        status = escape(item.status.value)
        title = escape(item.title)
        item_lines.append(f"{number}. <b>{title}</b> — {status} — {item.rating}/5")

    await callback.message.answer(
        ITEM_LEXICON_RU["list_title"].format(category=category_title)
        + "\n".join(item_lines),
        reply_markup=get_item_actions_keyboard(category_id),
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
    if not _is_http_url(image_url):
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
