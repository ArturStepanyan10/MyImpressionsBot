from database.models import Category
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

async def orm_get_all_categories(session: AsyncSession):
    query = select(Category)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_add_categories(session: AsyncSession, data: dict):
    obj = Category(
        title=data.get("title"),
        user_id=data.get("user_id")
    )
    session.add(obj)
    await session.commit()
    
    
async def orm_get_category(session: AsyncSession, category_id: int):
    query = select(Category).where(Category.id == category_id)
    result = await session.execute(query)
    return result.scalars().all()


async def orm_update_category(session: AsyncSession, category_id: int, data: dict):
    query = (
        update(Category)
        .where(Category.id == category_id)
        .values(
            title=data.get("title"),
            user_id=data.get("user_id")
        )
    )
    await session.execute(query)
    await session.commit()
    

async def orm_delete_category(session: AsyncSession, category_id: int):
    query = delete(Category).where(Category.id == category_id)
    await session.execute(query)
    await session.commit()