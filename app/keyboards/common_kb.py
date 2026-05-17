from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


cancel_btn = KeyboardButton(text="Отменить")
back_btn = KeyboardButton(text="Назад")

cancel_kb = ReplyKeyboardMarkup(keyboard=[[cancel_btn]], resize_keyboard=True)
back_kb = ReplyKeyboardMarkup(keyboard=[[back_btn]], resize_keyboard=True)

common_btns = {
    "cancel": cancel_kb,
    "back": back_kb,
}