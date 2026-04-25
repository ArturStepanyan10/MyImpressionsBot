from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Текст кнопок для клавиатуры
text_list = ["Ваши категории", "Добавить категорию", "Изменить категорию", "Удалить категорию"]

# Формируем клавиатуру из кнопок, размещая их по 2 в ряд
keyboard = [
    [KeyboardButton(text=text_list[i]), KeyboardButton(text=text_list[i + 1])]
    for i in range(0, len(text_list), 2)
]

# Определяем клавиатуру, которая будет отображаться пользователю
all_category_keyboard = ReplyKeyboardMarkup(
    keyboard=keyboard,
    resize_keyboard=True,
)