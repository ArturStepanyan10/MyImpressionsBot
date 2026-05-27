from typing import Optional, Union
from unicodedata import category
from aiogram.types import Message, CallbackQuery
from app.database.models import Category
from app.database.orm_queries.orm_query_category import (
    orm_add_categories,
    orm_get_category_by_id,
    orm_get_category_by_title,
    orm_update_category,
)
from app.states.forms_state import FSMFillFormCategoryState
from app.keyboards.common_kb import common_btns
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.lexicon.lexicon import CATEGORY_LEXICON_RU


Target = Union[Message, CallbackQuery]


class CategoryService:
    """
    Сервис для работы с категориями, который содержит общие функции для обработки категорий.
    """

    @staticmethod
    async def start_process_add_category(target: Target, state: FSMContext):
        """
        Запускает процесс добавления категории 
        и переводит FSM в состояние ожидания.
        """
    
        await state.update_data(cancel_keyboard="all_category")
        await target.answer(
            text=CATEGORY_LEXICON_RU["add_title_prompt"],
            reply_markup=common_btns["cancel"]
        )
    
        # Устанавливаем состояние ожидания ввода имени
        await state.set_state(FSMFillFormCategoryState.fill_add_title)
    
    @staticmethod 
    async def create_category(data: dict, session: AsyncSession) -> None:
        """Создаёт новую категорию и сохраняет её в базе данных."""
        
        await orm_add_categories(session, data)

    @staticmethod
    async def get_category_by_title(title: str, session: AsyncSession) -> Category | None:
        """Возвращает категорию с таким названием, если она уже есть."""

        return await orm_get_category_by_title(session, title)
    

    @staticmethod
    async def validate_update_and_delete_process(
        callback: CallbackQuery,
        category_id: int,
        db_user_id: int,
        session: AsyncSession
    ) -> Category | None:
        """
        Проверяет существование категории и доступ пользователя к ней.
        """

        category = await orm_get_category_by_id(session, category_id)

        if category is None:
            await callback.message.answer(
                CATEGORY_LEXICON_RU["not_found"],
                reply_markup=all_category_keyboard
            )
            return None

        if category.user_id != db_user_id:
            await callback.answer(
                CATEGORY_LEXICON_RU["not_owner"],
                show_alert=True
            )
            return None

        return category

    @staticmethod
    async def update_category(category_id: int, upd_data: dict, session: AsyncSession) -> None:
        """Обновляет информацию о категории в базе данных."""
        
        await orm_update_category(session, category_id, upd_data)
        
