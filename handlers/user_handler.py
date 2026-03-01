from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.basic import category_kb

router = Router()


@router.message(CommandStart())
async def process_start_command(message: Message):
    await message.answer(
        "Приветствую тебя, дорогой пользователь!", reply_markup=category_kb
    )


@router.message(F.text == "Категории")
async def process_select_category_button(message: Message):
    await message.answer(text="Вы открыли ваши категории")
