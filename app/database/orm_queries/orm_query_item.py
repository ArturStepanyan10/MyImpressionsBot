from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ItemStatus
from app.database.models import Category, Item

ITEMS_PER_PAGE = 10


class ORMQueryItem:
    """Запросы к предметам конкретной категории пользователя."""

    _CREATE_FIELDS = {"title", "review", "rating", "image_url", "status"}
    _UPDATE_FIELDS = {"title", "review", "rating", "image_url", "status"}

    def __init__(
        self,
        session: AsyncSession,
        category_id: int,
        user_id: int,
    ):
        self.session = session
        self.category_id = category_id
        self.user_id = user_id

    def _owned_category_ids(self):
        """Возвращает запрос с ID выбранной категории пользователя."""

        return select(Category.id).where(
            Category.id == self.category_id,
            Category.user_id == self.user_id,
        )

    async def get_all_items(self) -> list[Item]:
        """Возвращает все предметы из выбранной категории пользователя."""

        query = (
            select(Item)
            .where(Item.category_id.in_(self._owned_category_ids()))
            .order_by(Item.id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_items_page(
        self,
        page: int = 0,
        status: ItemStatus | None = None,
    ) -> tuple[list[Item], int, int]:
        """Возвращает элементы, актуальный номер страницы и число страниц."""

        conditions = [Item.category_id.in_(self._owned_category_ids())]
        if status is not None:
            conditions.append(Item.status == status)
        count_result = await self.session.execute(
            select(func.count()).select_from(Item).where(*conditions)
        )
        total = count_result.scalar_one()
        total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        # Старые кнопки могут указывать на страницу, исчезнувшую после удаления.
        page = min(max(0, page), total_pages - 1)
        result = await self.session.execute(
            select(Item)
            .where(*conditions)
            .order_by(Item.id)
            .limit(ITEMS_PER_PAGE)
            .offset(page * ITEMS_PER_PAGE)
        )
        return list(result.scalars().all()), page, total_pages

    async def get_item_by_id(self, item_id: int) -> Item | None:
        """Возвращает предмет только из принадлежащей пользователю категории."""

        query = select(Item).where(
            Item.id == item_id,
            Item.category_id.in_(self._owned_category_ids()),
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def add_item(self, data: Mapping[str, Any]) -> Item | None:
        """
        Добавляет предмет в выбранную категорию.

        Возвращает None, если категория не существует или принадлежит другому
        пользователю.
        """

        category_id = await self.session.scalar(self._owned_category_ids())
        if category_id is None:
            return None

        unknown_fields = set(data) - self._CREATE_FIELDS
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Недопустимые поля предмета: {fields}")

        item_data = dict(data)
        item_data["category_id"] = category_id

        item = Item(**item_data)
        self.session.add(item)
        await self.session.flush()
        return item

    async def patch_item(
        self,
        item_id: int,
        data: Mapping[str, Any],
    ) -> bool:
        """
        Частично обновляет предмет выбранной категории.

        Возвращает True, если предмет найден и обновлён.
        """

        unknown_fields = set(data) - self._UPDATE_FIELDS
        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Недопустимые поля для обновления: {fields}")

        if not data:
            return False

        query = (
            update(Item)
            .where(
                Item.id == item_id,
                Item.category_id.in_(self._owned_category_ids()),
            )
            .values(**dict(data))
        )
        result = await self.session.execute(query)
        return result.rowcount > 0

    async def delete_item(self, item_id: int) -> bool:
        """
        Удаляет предмет выбранной категории.

        Возвращает True, если предмет найден и удалён.
        """

        query = delete(Item).where(
            Item.id == item_id,
            Item.category_id.in_(self._owned_category_ids()),
        )
        result = await self.session.execute(query)
        return result.rowcount > 0

    async def get_items_by_status(self, status: ItemStatus) -> list[Item]:
        """Возвращает предметы выбранной категории с указанным статусом."""

        query = (
            select(Item)
            .where(
                Item.category_id.in_(self._owned_category_ids()),
                Item.status == status,
            )
            .order_by(Item.id)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
