from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Создаем объекты инлайн кнопок
add_category_inline_btn = InlineKeyboardButton(
    text="Добавить категорию",
    callback_data="add_category"
)


# Создаем объект инлайн клавиатуры, добавляя в него кнопки
add_category_inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[[add_category_inline_btn]])


def get_category_inline_keyboard(categories):
    
    categories_inline_btn = [InlineKeyboardButton(text=category.title, callback_data=f"category_{category.id}") 
                    for category in categories]
    
    return InlineKeyboardMarkup(inline_keyboard=[[btn] for btn in categories_inline_btn])
