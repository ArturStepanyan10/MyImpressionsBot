import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from lexicon.lexicon import LEXICON_RU
from database.orm_queries.orm_query_category import orm_delete_category, orm_get_all_categories, orm_get_category_by_id, orm_update_category
from keyboards.category_kb.basic_kb import all_category_keyboard
from keyboards.category_kb.inline_kb import add_category_inline_keyboard, get_category_inline_keyboard
from aiogram.fsm.context import FSMContext
from states.form_category_state import FSMFillFormCategoryState
from database.models import User
from database.orm_queries.orm_query_category import orm_add_categories
from keyboards.common_kb import common_btns



router = Router()
TITLE_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9\s\-]{0,49}$")


@router.message(CommandStart())
async def process_start_command(message: Message, db_user: User):
    await message.answer(f"Приветствую тебя, дорогой {db_user.name}! 👋 \n\n{LEXICON_RU.get('/start')}", 
                         reply_markup=all_category_keyboard)


@router.message(F.text == "/help")
async def process_help_command(message: Message):
    await message.answer(LEXICON_RU.get("/help"))
    

# Хэндлер обработки команды ОТМЕНА, которая будет срабатывать в любом состоянии и очищать его
@router.message(StateFilter("*"), F.text == "Отменить")
async def process_cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(text="Действие отменено 😕", reply_markup=all_category_keyboard)


@router.message(F.text == "Ваши категории")
async def process_select_category_button(message: Message, session: AsyncSession):
    action = "list"
    categories = await orm_get_all_categories(session)
    if categories:
        await message.answer(text=f"👇", reply_markup=get_category_inline_keyboard(categories, action))
    else:
        await message.answer(text="У вас пока нет категорий... \n\n Хотите добавить ?", reply_markup=add_category_inline_keyboard)
        
        
# Хэндлер срабатывает на команду ДОБАВИТЬ КАТЕГОРИЮ 
# и переводит бота в состояние ожидания ввода названия
@router.message(F.text == "Добавить категорию")
async def process_fillform_category_command(message: Message, state: FSMContext):
    await message.answer(text="Введите название категории", reply_markup=common_btns["cancel"])
    
    # Устанавливаем состояние ожидания ввода имени
    await state.set_state(FSMFillFormCategoryState.fill_add_title)
   
    
@router.message(
    StateFilter(FSMFillFormCategoryState.fill_add_title),
    F.text.func(lambda text: bool(text and TITLE_PATTERN.fullmatch(text.strip()))),
)
async def process_title_sent(
        message: Message, state: FSMContext, session: AsyncSession, db_user: User
    ):
    
    # Сохраняем введенное название имя в хранилище по ключу "title"
    title = message.text.strip()
    await state.update_data(title=title)
    await message.answer(text="Ооо, название бомба, честно говоря! 🤙")
    
    # Получаем данные из хранилища
    data = await state.get_data()
    
    await orm_add_categories(
        session=session,
        data={
            "title": data.get("title"),
            "user_id": db_user.id,
        },
    )
    
    # Выходит из состояния (Диалог закончен)
    await state.clear()
    await message.answer(text="Категория успешно добавлена!", reply_markup=all_category_keyboard)


# Этот хэндлер будет срабатывать, если во время ввода имени
# будет введено что-то некорректное
@router.message(StateFilter(FSMFillFormCategoryState.fill_add_title))
async def warning_not_title(message: Message):
    await message.answer(text="Брат, введи корректное название\n\n" 
                         "или ты думаешь, что самый крутой ?")
    

# Этот хэндлер срабатывает на инлайн кнопку ДОБАВИТЬ КАТЕГОРИЮ
# И переводит бота в состояние ожидания ввода названия
@router.callback_query(F.data == "add_category")
async def process_add_category_inline(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(text="Введите название категории")
    
    # Устанавливаем состояние ожидания ввода имени
    await state.set_state(FSMFillFormCategoryState.fill_add_title)
    

@router.message(F.text.in_(["Изменить категорию", "Удалить категорию"]))
async def process_update_category(message: Message, session: AsyncSession):
    action = "update" if message.text.startswith("Изменить") else "delete"
    
    categories = await orm_get_all_categories(session)
    await message.answer(text="Выберите категорию", reply_markup=get_category_inline_keyboard(categories, action))


@router.callback_query(F.data.startswith("update_category_"))
async def process_selected_category(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    category_id = int(callback.data.split("_")[-1])
    category = await orm_get_category_by_id(session, category_id)
    
    # Сохраняем ID категории в состоянии для дальнейшего использования при обновлении
    await state.set_state(FSMFillFormCategoryState.fill_category_id)
    await state.update_data(category_id=category_id)
    
    await callback.answer()
    # Устанавливаем состояние ожидания ввода нового названия
    await state.set_state(FSMFillFormCategoryState.fill_update_title)
    await callback.message.answer(f"Название категории: <b>{category.title}</b> \n\n Напишите новое название для категории", reply_markup=common_btns["cancel"])


@router.message(
    StateFilter(FSMFillFormCategoryState.fill_update_title),
    F.text.func(lambda text: bool(text and TITLE_PATTERN.fullmatch(text.strip()))),
)
async def process_update_category_title(message: Message, session: AsyncSession, state: FSMContext, db_user: User):

    new_title = message.text.strip()
    
    # Сохраняем новое название в состоянии
    await state.update_data(title=new_title)
    data = await state.get_data()
    
    upd_data = {
        "title": data.get("title"),
        "user_id": db_user.id,
    }
    
    await orm_update_category(session, data.get("category_id"), upd_data)
    await message.answer("Категория успешно обновлена! ✅", reply_markup=all_category_keyboard)
    

@router.callback_query(F.data.startswith("delete_category_"))
async def process_delete_category(callback: CallbackQuery, session: AsyncSession):
    category_id = int(callback.data.split("_")[-1])
    
    await orm_delete_category(session, category_id)
    
    await callback.message.answer("Категория успешно удалена! ✅", reply_markup=all_category_keyboard)
    #await callback.message.answer(f"Вы уверены, что хотите удалить категорию <b>{category.title}</b> ? 
    # \n\n Это действие нельзя будет отменить!", reply_markup=common_btns["confirm_delete"])