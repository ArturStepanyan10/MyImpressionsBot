from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_item_actions_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Возвращает действия, доступные внутри категории."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Добавить элемент",
                    callback_data=f"add_item_{category_id}",
                )
            ]
        ]
    )


def get_item_created_keyboard(category_id: int) -> InlineKeyboardMarkup:
    """Возвращает действия после успешного добавления элемента."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Вернуться к элементам",
                    callback_data=f"list_category_{category_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Добавить ещё",
                    callback_data=f"add_item_{category_id}",
                )
            ],
        ]
    )
