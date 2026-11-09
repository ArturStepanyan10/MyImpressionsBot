from html import escape

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.orm_queries.orm_query_item import ORMQueryItem
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.common_kb import common_btns
from app.keyboards.item_kb.callbacks import (
    ITEM_STATUS_FILTERS,
    ItemActionCallback,
    ItemEditFieldCallback,
    ItemSetStatusCallback,
)
from app.keyboards.item_kb.inline_kb import (
    get_item_delete_keyboard,
    get_item_details_keyboard,
    get_item_edit_keyboard,
    get_item_status_keyboard,
)
from app.lexicon.lexicon import ITEM_LEXICON_RU
from app.services.category_services import CategoryService
from app.services.item_services import (
    EDITABLE_ITEM_FIELDS,
    clear_item_form,
    get_callback_item,
    send_category_items,
    send_item_card,
    validate_item_field,
)
from app.states.forms_state import FSMEditItemState

router = Router()


@router.callback_query(ItemActionCallback.filter())
async def process_item_action(
    callback: CallbackQuery,
    callback_data: ItemActionCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    """Открывает меню карточки или выполняет подтверждённое удаление."""

    action = callback_data.action
    if action not in {"edit", "status", "delete", "confirm_delete"}:
        await callback.answer(ITEM_LEXICON_RU["invalid_action"], show_alert=True)
        return
    item = await get_callback_item(callback, callback_data, session, db_user.id)
    if item is None:
        return
    await clear_item_form(callback.message, state)
    if action == "confirm_delete":
        category = await CategoryService.get_owned_category(
            callback, item.category_id, db_user.id, session
        )
        if category is None:
            return
        deleted = await ORMQueryItem(session, item.category_id, db_user.id).delete_item(
            item.id
        )
        if not deleted:
            await callback.answer(ITEM_LEXICON_RU["item_unavailable"], show_alert=True)
            return
        await callback.answer(ITEM_LEXICON_RU["delete_success"])
        await send_category_items(
            callback.message,
            session,
            category,
            db_user.id,
            callback_data.status,
            callback_data.page,
        )
        return

    if action == "edit":
        text = ITEM_LEXICON_RU["edit_menu"]
        keyboard = get_item_edit_keyboard(callback_data)
    elif action == "status":
        text = ITEM_LEXICON_RU["status_menu"]
        keyboard = get_item_status_keyboard(callback_data, item.status)
    else:
        text = ITEM_LEXICON_RU["delete_prompt"]
        keyboard = get_item_delete_keyboard(callback_data)
    await callback.answer()
    await callback.message.answer(
        text.format(title=escape(item.title)), reply_markup=keyboard
    )


@router.callback_query(ItemEditFieldCallback.filter())
async def process_item_edit_field(
    callback: CallbackQuery,
    callback_data: ItemEditFieldCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    """Начинает ввод нового значения с контекстом элемента и списка."""

    if callback_data.field not in EDITABLE_ITEM_FIELDS:
        await callback.answer(ITEM_LEXICON_RU["invalid_action"], show_alert=True)
        return
    item = await get_callback_item(callback, callback_data, session, db_user.id)
    if item is None:
        return
    await state.set_data(
        {
            "category_id": item.category_id,
            "item_id": item.id,
            "field": callback_data.field,
            "list_status": callback_data.status,
            "list_page": callback_data.page,
            "cancel_keyboard": "item_card",
        }
    )
    await state.set_state(FSMEditItemState.fill_value)
    await callback.answer()
    await callback.message.answer(
        ITEM_LEXICON_RU[f"edit_{callback_data.field}_prompt"],
        reply_markup=common_btns["cancel"],
    )


@router.message(StateFilter(FSMEditItemState.fill_value))
async def process_item_edit_value(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    """Проверяет новое значение и показывает карточку после сохранения."""

    data = await state.get_data()
    required = {"category_id", "item_id", "field"}
    if (
        not required.issubset(data)
        or data["field"] not in EDITABLE_ITEM_FIELDS
        or data.get("list_status", "all") not in ITEM_STATUS_FILTERS
        or not isinstance(data.get("list_page", 0), int)
        or not 0 <= data.get("list_page", 0) <= 2_147_483_647
    ):
        await state.clear()
        await message.answer(
            ITEM_LEXICON_RU["edit_expired"], reply_markup=all_category_keyboard
        )
        return
    try:
        value = validate_item_field(data["field"], message.text or "")
    except ValueError as error:
        await message.answer(ITEM_LEXICON_RU[str(error)])
        return

    queries = ORMQueryItem(session, data["category_id"], db_user.id)
    updated = await queries.patch_item(data["item_id"], {data["field"]: value})
    item = await queries.get_item_by_id(data["item_id"]) if updated else None
    await state.clear()
    if item is None:
        await message.answer(
            ITEM_LEXICON_RU["item_unavailable"], reply_markup=all_category_keyboard
        )
        return
    await message.answer(
        ITEM_LEXICON_RU["edit_success"], reply_markup=all_category_keyboard
    )
    await send_item_card(
        message,
        item,
        get_item_details_keyboard(
            item.category_id,
            item.id,
            data.get("list_status", "all"),
            data.get("list_page", 0),
        ),
    )


@router.callback_query(ItemSetStatusCallback.filter())
async def process_item_set_status(
    callback: CallbackQuery,
    callback_data: ItemSetStatusCallback,
    session: AsyncSession,
    db_user: User,
    state: FSMContext,
) -> None:
    """Меняет статус сразу, проверяя доступ и сохраняя контекст фильтра."""

    new_status = ITEM_STATUS_FILTERS.get(callback_data.new_status)
    if new_status is None:
        await callback.answer(ITEM_LEXICON_RU["invalid_action"], show_alert=True)
        return
    item = await get_callback_item(callback, callback_data, session, db_user.id)
    if item is None:
        return
    await clear_item_form(callback.message, state)
    queries = ORMQueryItem(session, item.category_id, db_user.id)
    updated = await queries.patch_item(item.id, {"status": new_status})
    item = await queries.get_item_by_id(item.id) if updated else None
    if item is None:
        await callback.answer(ITEM_LEXICON_RU["item_unavailable"], show_alert=True)
        return
    await callback.answer(ITEM_LEXICON_RU["status_success"])
    await send_item_card(
        callback.message,
        item,
        get_item_details_keyboard(
            item.category_id, item.id, callback_data.status, callback_data.page
        ),
    )
