from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Category


async def orm_get_all_categories(session: AsyncSession):
    """
    Получает список всех категорий из базы данных.
    """
    query = select(Category)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_get_category_by_title(session: AsyncSession, title: str):
    """
    Получает категорию по её названию.
    Возвращает объект Category или None.
    """
    query = select(Category).where(Category.title == title)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_add_categories(session: AsyncSession, data: dict):
    """
    Создает и добавляет новую категорию в базу данных.
    """
    obj = Category(title=data.get("title"), user_id=data.get("user_id"))

    # Сохраняем категорию в БД (commit происходит в middleware)
    session.add(obj)
    await session.flush()
    return obj


async def orm_get_category_by_id(session: AsyncSession, category_id: int):
    """
    Получает категорию по её ID.
    Возвращает объект Category или None.
    """
    query = select(Category).where(Category.id == category_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def orm_update_category(session: AsyncSession, category_id: int, data: dict):
    """
    Обновляет данные категории по её ID.
    """
    query = (
        update(Category)
        .where(Category.id == category_id)
        .values(title=data.get("title"), user_id=data.get("user_id"))
    )
    await session.execute(query)
    await session.commit()


async def orm_delete_category(session: AsyncSession, category_id: int):
    """
    Удаляет категорию по её ID.
    """
    query = delete(Category).where(Category.id == category_id)
    await session.execute(query)
    await session.commit()
