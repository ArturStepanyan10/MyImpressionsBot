from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.enums import ItemStatus
from app.database.models import Item
from app.keyboards.item_kb.callbacks import (
    ITEM_STATUS_FILTERS,
    ItemActionCallback,
    ItemDetailsCallback,
    ItemEditFieldCallback,
    ItemListCallback,
    ItemSetStatusCallback,
)
from app.lexicon.lexicon import ITEM_LEXICON_RU


def get_item_list_keyboard(
    category_id: int,
    items: list[Item],
    status: str = "all",
) -> InlineKeyboardMarkup:
    """Список элементов, фильтры и переходы внутри категории."""

    rows = [
        [
            InlineKeyboardButton(
                text=ITEM_LEXICON_RU["item_button"].format(
                    title=item.title[:50],
                    rating=item.rating,
                    status=item.status.value,
                ),
                callback_data=ItemDetailsCallback(
                    category_id=category_id, item_id=item.id, status=status
                ).pack(),
            )
        ]
        for item in items
    ]
    filters = [
        InlineKeyboardButton(
            text=("✓ " if key == status else "") + ITEM_LEXICON_RU[f"filter_{key}"],
            callback_data=ItemListCallback(category_id=category_id, status=key).pack(),
        )
        for key in ITEM_STATUS_FILTERS
    ]
    rows.extend([filters[:2], filters[2:]])
    rows.extend(get_item_actions_keyboard(category_id).inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_item_details_keyboard(
    category_id: int, item_id: int, status: str = "all"
) -> InlineKeyboardMarkup:
    """Действия с элементом и возврат к списку с выбранным фильтром."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU[f"action_{action}"],
                    callback_data=ItemActionCallback(
                        category_id=category_id,
                        item_id=item_id,
                        status=status,
                        action=action,
                    ).pack(),
                )
            ]
            for action in ("edit", "status", "delete")
        ]
        + [
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU["back"],
                    callback_data=ItemListCallback(
                        category_id=category_id, status=status
                    ).pack(),
                )
            ]
        ]
    )


def get_item_edit_keyboard(data: ItemDetailsCallback) -> InlineKeyboardMarkup:
    """Выбор поля для изменения и возврат в карточку."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU[f"field_{field}"],
                    callback_data=ItemEditFieldCallback(
                        category_id=data.category_id,
                        item_id=data.item_id,
                        status=data.status,
                        field=field,
                    ).pack(),
                )
            ]
            for field in ("title", "review", "rating", "image_url")
        ]
        + [[_back_to_card_button(data)]]
    )


def get_item_status_keyboard(
    data: ItemDetailsCallback, current_status: ItemStatus
) -> InlineKeyboardMarkup:
    """Выбор одного из трёх статусов без запуска формы."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✓ " if status == current_status else "")
                    + ITEM_LEXICON_RU[f"filter_{key}"],
                    callback_data=ItemSetStatusCallback(
                        category_id=data.category_id,
                        item_id=data.item_id,
                        status=data.status,
                        new_status=key,
                    ).pack(),
                )
            ]
            for key, status in ITEM_STATUS_FILTERS.items()
            if status is not None
        ]
        + [[_back_to_card_button(data)]]
    )


def get_item_delete_keyboard(data: ItemDetailsCallback) -> InlineKeyboardMarkup:
    """Подтверждение удаления отдельным нажатием."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU["delete_confirm"],
                    callback_data=ItemActionCallback(
                        category_id=data.category_id,
                        item_id=data.item_id,
                        status=data.status,
                        action="confirm_delete",
                    ).pack(),
                )
            ],
            [_back_to_card_button(data, ITEM_LEXICON_RU["delete_cancel"])],
        ]
    )


def _back_to_card_button(
    data: ItemDetailsCallback, text: str = ITEM_LEXICON_RU["back"]
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=ItemDetailsCallback(
            category_id=data.category_id, item_id=data.item_id, status=data.status
        ).pack(),
    )


def get_item_actions_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Возвращает действия, доступные внутри категории."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU["add_item"],
                    callback_data=f"add_item_{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU["back_to_categories"],
                    callback_data="item_categories",
                )
            ],
        ]
    )


def get_item_created_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Возвращает действия после успешного добавления элемента."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU["back_to_items"],
                    callback_data=f"list_category_{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=ITEM_LEXICON_RU["add_another"],
                    callback_data=f"add_item_{category_id}",
                )
            ],
        ]
    )
