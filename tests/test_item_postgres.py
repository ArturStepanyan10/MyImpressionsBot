import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import DefaultKeyBuilder, StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ItemStatus
from app.database.orm_queries.orm_query_item import ORMQueryItem
from app.handlers.item_action_hndlrs import (
    process_item_action,
    process_item_edit_field,
    process_item_edit_value,
    process_item_set_status,
)
from app.keyboards.item_kb.callbacks import (
    ItemActionCallback,
    ItemEditFieldCallback,
    ItemSetStatusCallback,
)


@unittest.skipUnless(
    os.environ.get("RUN_POSTGRES_TESTS") == "1",
    "Для проверки PostgreSQL установи RUN_POSTGRES_TESTS=1 и POSTGRES_URL в .env",
)
class ItemPostgresTests(unittest.IsolatedAsyncioTestCase):
    """Проверяет совместимость модели с существующей колонкой VARCHAR(20)."""

    async def test_status_filter_creation_and_update_with_varchar_column(self):
        from app.database.engine import engine

        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    # Временные таблицы перекрывают реальные только в этой сессии.
                    # Откат удаляет их вместе с тестовыми данными.
                    await connection.execute(
                        text(
                            "CREATE TEMP TABLE category ("
                            "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, "
                            "title VARCHAR(255) NOT NULL, "
                            "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
                            "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                            ") ON COMMIT DROP"
                        )
                    )
                    await connection.execute(
                        text(
                            "CREATE TEMP TABLE item ("
                            "id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL, "
                            "review TEXT, rating SMALLINT, image_url TEXT, "
                            "category_id INTEGER NOT NULL, "
                            "status VARCHAR(20) NOT NULL, "
                            "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
                            "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                            ") ON COMMIT DROP"
                        )
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO pg_temp.category (id, user_id, title) VALUES (1, 1, 'Owned'), (2, 2, 'Foreign')"
                        )
                    )
                    await connection.execute(
                        text(
                            "INSERT INTO pg_temp.item (title, category_id, status) "
                            "VALUES ('Planned', 1, 'PLANNED'), "
                            "('In progress', 1, 'IN_PROGRESS'), "
                            "('Completed', 1, 'COMPLETED'), "
                            "('Foreign', 2, 'PLANNED')"
                        )
                    )
                    async with AsyncSession(
                        bind=connection, expire_on_commit=False
                    ) as session:
                        queries = ORMQueryItem(session, category_id=1, user_id=1)
                        for status, expected_title in (
                            (ItemStatus.PLANNED, "Planned"),
                            (ItemStatus.IN_PROGRESS, "In progress"),
                            (ItemStatus.COMPLETED, "Completed"),
                        ):
                            with self.subTest(status=status):
                                items = await queries.get_items_by_status(status)
                                self.assertEqual(
                                    [item.title for item in items], [expected_title]
                                )
                                self.assertIs(items[0].status, status)

                        item = await queries.add_item(
                            {"title": "Created", "review": "Review", "rating": 5}
                        )
                        self.assertIs(item.status, ItemStatus.PLANNED)
                        self.assertTrue(
                            await queries.patch_item(
                                item.id, {"status": ItemStatus.IN_PROGRESS}
                            )
                        )
                        await session.refresh(item)
                        self.assertIs(item.status, ItemStatus.IN_PROGRESS)
                        stored_status = await connection.scalar(
                            text("SELECT status FROM pg_temp.item WHERE id = :id"),
                            {"id": item.id},
                        )
                        self.assertEqual(stored_status, "IN_PROGRESS")
                        await self.check_card_actions(session, queries, item.id)
                finally:
                    await transaction.rollback()
        finally:
            await engine.dispose()

    async def check_card_actions(self, session, queries, item_id):
        storage = (
            RedisStorage.from_url(
                os.environ.get("TEST_REDIS_URL", "redis://localhost:6380/0"),
                key_builder=DefaultKeyBuilder(prefix=f"item-test:{uuid4().hex}"),
            )
            if os.environ.get("RUN_REDIS_TESTS") == "1"
            else MemoryStorage()
        )
        state = FSMContext(
            storage=storage, key=StorageKey(bot_id=1, chat_id=1, user_id=1)
        )
        message = SimpleNamespace(
            text=None, answer=AsyncMock(), answer_photo=AsyncMock()
        )
        callback = SimpleNamespace(answer=AsyncMock(), message=message)
        user = SimpleNamespace(id=1)
        context = {"category_id": 1, "item_id": item_id, "status": "planned"}
        try:
            for field, value, expected in (
                ("title", "Updated", "Updated"),
                ("review", "Updated review", "Updated review"),
                ("rating", "4", 4),
                (
                    "image_url",
                    "https://example.com/new.jpg",
                    "https://example.com/new.jpg",
                ),
            ):
                with self.subTest(field=field):
                    await process_item_edit_field(
                        callback,
                        ItemEditFieldCallback(**context, field=field),
                        session,
                        user,
                        state,
                    )
                    message.text = value
                    await process_item_edit_value(message, state, session, user)
                    item = await queries.get_item_by_id(item_id)
                    self.assertEqual(getattr(item, field), expected)
                    self.assertIsNone(await state.get_state())
            for key, status in (
                ("planned", ItemStatus.PLANNED),
                ("progress", ItemStatus.IN_PROGRESS),
                ("completed", ItemStatus.COMPLETED),
            ):
                await process_item_set_status(
                    callback,
                    ItemSetStatusCallback(**context, new_status=key),
                    session,
                    user,
                    state,
                )
                item = await queries.get_item_by_id(item_id)
                self.assertIs(item.status, status)
            await process_item_action(
                callback,
                ItemActionCallback(**context, action="delete"),
                session,
                user,
                state,
            )
            self.assertIsNotNone(await queries.get_item_by_id(item_id))
            await process_item_action(
                callback,
                ItemActionCallback(**context, action="confirm_delete"),
                session,
                user,
                state,
            )
            self.assertIsNone(await queries.get_item_by_id(item_id))
        finally:
            await state.clear()
            await storage.close()


if __name__ == "__main__":
    unittest.main()
