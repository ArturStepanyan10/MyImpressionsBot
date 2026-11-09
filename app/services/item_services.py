from html import escape
from urllib.parse import urlparse

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Category, Item
from app.database.orm_queries.orm_query_item import ORMQueryItem
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.item_kb.callbacks import ITEM_STATUS_FILTERS, ItemDetailsCallback
from app.keyboards.item_kb.inline_kb import (
    get_item_details_keyboard,
    get_item_list_keyboard,
)
from app.lexicon.lexicon import ITEM_LEXICON_RU

EDITABLE_ITEM_FIELDS = {"title", "review", "rating", "image_url"}


def is_http_url(value: str) -> bool:
    try:
        parsed_url = urlparse(value)
        return parsed_url.scheme in {"http", "https"} and bool(parsed_url.hostname)
    except ValueError:
        return False


def validate_item_field(field: str, value: str) -> str | int:
    """Проверяет значение; при ошибке передаёт ключ сообщения через ValueError."""

    value = value.strip()
    if field == "title" and 1 <= len(value) <= 255:
        return value
    if field == "review" and value:
        return value
    if field == "rating" and value in {"1", "2", "3", "4", "5"}:
        return int(value)
    if field == "image_url" and is_http_url(value):
        return value
    raise ValueError(f"invalid_{field}")


async def get_callback_item(
    callback: CallbackQuery,
    data: ItemDetailsCallback,
    session: AsyncSession,
    user_id: int,
) -> Item | None:
    """Проверяет фильтр и доступ к элементу для каждого действия карточки."""

    if data.status not in ITEM_STATUS_FILTERS:
        await callback.answer(ITEM_LEXICON_RU["invalid_filter"], show_alert=True)
        return None
    item = await ORMQueryItem(session, data.category_id, user_id).get_item_by_id(
        data.item_id
    )
    if item is None:
        await callback.answer(ITEM_LEXICON_RU["item_unavailable"], show_alert=True)
    return item


async def clear_item_form(message: Message, state: FSMContext) -> None:
    """Выход по inline-навигации прекращает незавершённый ввод."""

    if await state.get_state() is not None:
        await state.clear()
        await message.answer(
            ITEM_LEXICON_RU["form_cancelled"], reply_markup=all_category_keyboard
        )


async def cancel_item_edit(
    message: Message, state: FSMContext, session: AsyncSession, user_id: int
) -> None:
    """Отменяет ввод и возвращает к актуальной карточке, если она доступна."""

    data = await state.get_data()
    await state.clear()
    await message.answer(
        ITEM_LEXICON_RU["edit_cancelled"], reply_markup=all_category_keyboard
    )
    if not {"category_id", "item_id"}.issubset(data):
        await message.answer(ITEM_LEXICON_RU["edit_expired"])
        return
    item = await ORMQueryItem(session, data["category_id"], user_id).get_item_by_id(
        data["item_id"]
    )
    if item is None:
        await message.answer(ITEM_LEXICON_RU["item_unavailable"])
        return
    status = data.get("list_status", "all")
    await send_item_card(
        message,
        item,
        get_item_details_keyboard(
            item.category_id, item.id, status, data.get("list_page", 0)
        ),
    )


async def send_category_items(
    message: Message,
    session: AsyncSession,
    category: Category,
    user_id: int,
    status: str = "all",
    page: int = 0,
) -> None:
    """Выводит список, в том числе после удаления элемента."""

    queries = ORMQueryItem(session, category.id, user_id)
    status_filter = ITEM_STATUS_FILTERS[status]
    items, page, total_pages = await queries.get_items_page(page, status_filter)
    category_title = escape(category.title)
    if status == "all":
        text = ITEM_LEXICON_RU["list_title" if items else "list_empty"].format(
            category=category_title
        )
    else:
        text = ITEM_LEXICON_RU["list_filtered" if items else "filter_empty"].format(
            category=category_title,
            status=ITEM_LEXICON_RU[f"filter_{status}"],
        )
    text = (
        text.rstrip()
        + "\n\n"
        + ITEM_LEXICON_RU["page_number"].format(page=page + 1, total_pages=total_pages)
    )
    await message.answer(
        text,
        reply_markup=get_item_list_keyboard(
            category.id, items, status, page, total_pages
        ),
    )


def get_item_card_parts(item: Item, *, image_link: bool = False) -> list[str]:
    """Разбивает неограниченный отзыв на сообщения, сохраняя HTML-разметку."""

    header = ITEM_LEXICON_RU["card"].format(
        title=escape(item.title),
        rating=item.rating,
        status=escape(item.status.value),
        created_at=item.created_at.strftime("%d.%m.%Y"),
    )
    review = item.review or ITEM_LEXICON_RU["review_empty"]
    # Запас учитывает заголовок и символы вне BMP (две UTF-16 единицы).
    parts = [header + escape(review[:1200])]
    parts.extend(
        escape(review[offset : offset + 1800])
        for offset in range(1200, len(review), 1800)
    )
    if image_link and item.image_url:
        parts.append(
            ITEM_LEXICON_RU["image_link"].format(url=escape(item.image_url, quote=True))
        )
    return parts


async def send_item_card(
    message: Message, item: Item, keyboard: InlineKeyboardMarkup
) -> None:
    """Показывает изображение и карточку; недоступное фото заменяет ссылкой."""

    image_failed = False
    if item.image_url:
        try:
            await message.answer_photo(photo=item.image_url)
        except (TelegramBadRequest, TelegramNetworkError):
            image_failed = True

    parts = get_item_card_parts(item, image_link=image_failed)
    for index, part in enumerate(parts):
        await message.answer(
            part,
            reply_markup=keyboard if index == len(parts) - 1 else None,
        )
