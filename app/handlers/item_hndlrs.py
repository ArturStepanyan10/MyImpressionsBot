from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.orm_queries.orm_query_category import orm_get_category_by_id
from app.database.orm_queries.orm_query_item import ORMQueryItem
from app.lexicon.lexicon import CATEGORY_LEXICON_RU

router = Router()


@router.callback_query(F.data.startswith("list_category_"))
async def process_category_items(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: User,
) -> None:
    """Показывает список элементов выбранной категории пользователя."""

    category_id = int(callback.data.rsplit("_", maxsplit=1)[-1])
    category = await orm_get_category_by_id(session, category_id)

    if category is None:
        await callback.answer(CATEGORY_LEXICON_RU["not_found"], show_alert=True)
        return

    if category.user_id != db_user.id:
        await callback.answer(CATEGORY_LEXICON_RU["not_owner"], show_alert=True)
        return

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
            f"В категории <b>{category_title}</b> пока нет элементов."
        )
        return

    item_lines = []
    for number, item in enumerate(items, start=1):
        status = escape(item.status.value)
        title = escape(item.title)
        item_lines.append(f"{number}. <b>{title}</b> — {status} — {item.rating}/5")

    await callback.message.answer(
        f"Элементы категории <b>{category_title}</b>:\n\n" + "\n".join(item_lines)
    )
