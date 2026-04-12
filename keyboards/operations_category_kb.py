from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


button_add_category = KeyboardButton(text="Добавить категорию")
button_update_category = KeyboardButton(text="Изменить категорию")
button_delete_category = KeyboardButton(text="Удалить категорию")

keyboard = ReplyKeyboardMarkup(keyboard=[
        [button_add_category, button_update_category, button_delete_category]
    ],
    resize_keyboard=True
)