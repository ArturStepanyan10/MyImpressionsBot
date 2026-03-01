from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Кнопка категории
button_category = KeyboardButton(text="Категории")

# Инициализация билдер для клавиатуры с кнопкой "Категории"
button_builder = ReplyKeyboardBuilder()

# Добавляет кнопку в билдер
button_builder.row(button_category)

# Создает клавиатуры с кнопкой "Категории"
category_kb: ReplyKeyboardMarkup = button_builder.as_markup(
    one_time_keyboard=True, resize_keyboard=True
)
