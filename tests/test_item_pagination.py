import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.enums import ItemStatus
from app.database.models import Base, Category, Item, User
from app.database.orm_queries.orm_query_item import ITEMS_PER_PAGE, ORMQueryItem
from app.handlers.base_hndlrs import process_cancel_command
from app.handlers.item_action_hndlrs import (
    process_item_action,
    process_item_edit_field,
    process_item_edit_value,
    process_item_set_status,
)
from app.handlers.item_hndlrs import (
    process_filtered_category_items,
    process_item_details,
)
from app.keyboards.item_kb.callbacks import (
    ItemActionCallback,
    ItemDetailsCallback,
    ItemEditFieldCallback,
    ItemListCallback,
    ItemSetStatusCallback,
)


class ItemPaginationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        users = [
            User(name=str(i), last_name="", telegram_id=i, username=str(i))
            for i in (1, 2)
        ]
        self.db.add_all(users)
        self.db.flush()
        self.user = users[0]
        self.category = Category(title="Books", user_id=users[0].id)
        self.empty_category = Category(title="Empty", user_id=users[0].id)
        foreign_category = Category(title="Foreign", user_id=users[1].id)
        self.db.add_all([self.category, self.empty_category, foreign_category])
        self.db.flush()
        self.items = [
            Item(
                title=f"Item {i}",
                review="Review",
                rating=4,
                image_url="",
                category_id=self.category.id,
                status=ItemStatus.PLANNED if i < 21 else ItemStatus.COMPLETED,
            )
            for i in range(24)
        ]
        self.db.add_all(
            self.items
            + [
                Item(
                    title="Foreign",
                    review="Review",
                    rating=5,
                    image_url="",
                    category_id=foreign_category.id,
                    status=ItemStatus.PLANNED,
                )
            ]
        )
        self.db.commit()
        self.session = AsyncMock(spec=AsyncSession)
        self.session.execute.side_effect = self.db.execute
        self.state = FSMContext(
            MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1)
        )
        self.message = SimpleNamespace(
            text=None, answer=AsyncMock(), answer_photo=AsyncMock()
        )
        self.callback = SimpleNamespace(message=self.message, answer=AsyncMock())
        self.context = {
            "category_id": self.category.id,
            "item_id": self.items[20].id,
            "status": "planned",
            "page": 2,
        }

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def buttons(self):
        return [
            b
            for row in self.message.answer.call_args.kwargs[
                "reply_markup"
            ].inline_keyboard
            for b in row
        ]

    def item_callbacks(self):
        return [
            ItemDetailsCallback.unpack(b.callback_data)
            for b in self.buttons()
            if b.callback_data.startswith("item:")
        ]

    async def show_page(self, page, status="all", category_id=None):
        await process_filtered_category_items(
            self.callback,
            ItemListCallback(
                category_id=category_id or self.category.id, status=status, page=page
            ),
            self.session,
            self.user,
            self.state,
        )

    async def test_pages_cover_owned_items_once_with_bounded_keyboards(self):
        seen = []
        for page, expected_count in ((0, 10), (1, 10), (2, 4)):
            await self.show_page(page)
            data = self.item_callbacks()
            seen.extend(d.item_id for d in data)
            self.assertEqual(len(data), expected_count)
            self.assertTrue(all(d.page == page for d in data))
            self.assertIn(
                f"Страница {page + 1} из 3", self.message.answer.call_args.args[0]
            )
            self.assertLessEqual(len(self.buttons()), ITEMS_PER_PAGE + 8)
            arrows = [
                b
                for b in self.buttons()
                if "Предыдущая" in b.text or "Следующая" in b.text
            ]
            expected_pages = [p for p in (page - 1, page + 1) if 0 <= p < 3]
            self.assertEqual(
                [ItemListCallback.unpack(b.callback_data).page for b in arrows],
                expected_pages,
            )
        self.assertEqual(seen, [item.id for item in self.items])

    async def test_filter_navigation_preserves_status_and_filter_switch_resets_page(
        self,
    ):
        seen = []
        for page, expected_count in ((0, 10), (1, 10), (2, 1)):
            await self.show_page(page, "planned")
            data = self.item_callbacks()
            seen.extend(d.item_id for d in data)
            self.assertEqual(len(data), expected_count)
            self.assertTrue(all(d.status == "planned" for d in data))
            for button in self.buttons():
                if "Предыдущая" in button.text or "Следующая" in button.text:
                    self.assertEqual(
                        ItemListCallback.unpack(button.callback_data).status, "planned"
                    )
                if button.text.lstrip("✓ ") in {
                    "Все",
                    "Запланировано",
                    "В процессе",
                    "Выполнено",
                }:
                    self.assertEqual(
                        ItemListCallback.unpack(button.callback_data).page, 0
                    )
        self.assertEqual(seen, [item.id for item in self.items[:21]])
        await self.show_page(0, "completed")
        self.assertEqual(
            [d.item_id for d in self.item_callbacks()],
            [item.id for item in self.items[21:]],
        )

    async def test_outdated_page_is_clamped_and_empty_filter_has_no_arrows(self):
        await self.show_page(2_147_483_647, "planned")
        self.assertEqual(
            [d.item_id for d in self.item_callbacks()], [self.items[20].id]
        )
        self.assertEqual(self.item_callbacks()[0].page, 2)
        for status, category_id in (
            ("progress", self.category.id),
            ("all", self.empty_category.id),
        ):
            await self.show_page(100, status, category_id)
            self.assertEqual(self.item_callbacks(), [])
            self.assertIn("Страница 1 из 1", self.message.answer.call_args.args[0])
            self.assertFalse(
                any(
                    "Предыдущая" in b.text or "Следующая" in b.text
                    for b in self.buttons()
                )
            )
            self.assertTrue(any(b.text == "Добавить элемент" for b in self.buttons()))

    async def test_card_edit_save_and_cancel_keep_original_page(self):
        await process_item_details(
            self.callback,
            ItemDetailsCallback(**self.context),
            self.session,
            self.user,
            self.state,
        )
        for button in self.buttons()[:-1]:
            self.assertEqual(ItemActionCallback.unpack(button.callback_data).page, 2)
        back = ItemListCallback.unpack(self.buttons()[-1].callback_data)
        self.assertEqual((back.page, back.status), (2, "planned"))
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.context, action="edit"),
            self.session,
            self.user,
            self.state,
        )
        field = ItemEditFieldCallback.unpack(self.buttons()[0].callback_data)
        self.assertEqual(field.page, 2)
        self.assertEqual(
            ItemDetailsCallback.unpack(self.buttons()[-1].callback_data).page, 2
        )
        for save in (True, False):
            await process_item_edit_field(
                self.callback, field, self.session, self.user, self.state
            )
            self.assertEqual((await self.state.get_data())["list_page"], 2)
            if save:
                self.message.text = "Changed"
                await process_item_edit_value(
                    self.message, self.state, self.session, self.user
                )
            else:
                await process_cancel_command(
                    self.message, self.state, self.session, self.user
                )
            back = ItemListCallback.unpack(self.buttons()[-1].callback_data)
            self.assertEqual((back.page, back.status), (2, "planned"))
        await process_filtered_category_items(
            self.callback, back, self.session, self.user, self.state
        )
        self.assertEqual(self.item_callbacks()[0].item_id, self.context["item_id"])

    async def test_status_change_keeps_page_then_back_clamps_shrunken_filter(self):
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.context, action="status"),
            self.session,
            self.user,
            self.state,
        )
        target = ItemSetStatusCallback.unpack(self.buttons()[2].callback_data)
        self.assertEqual(target.page, 2)
        self.assertEqual(
            ItemDetailsCallback.unpack(self.buttons()[-1].callback_data).page, 2
        )
        await process_item_set_status(
            self.callback, target, self.session, self.user, self.state
        )
        back = ItemListCallback.unpack(self.buttons()[-1].callback_data)
        self.assertEqual((back.page, back.status), (2, "planned"))
        await process_filtered_category_items(
            self.callback, back, self.session, self.user, self.state
        )
        self.assertIn("Страница 2 из 2", self.message.answer.call_args.args[0])
        self.assertEqual(
            [d.item_id for d in self.item_callbacks()],
            [item.id for item in self.items[10:20]],
        )

    async def test_delete_last_item_on_last_page_returns_to_previous_page(self):
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.context, action="delete"),
            self.session,
            self.user,
            self.state,
        )
        confirm = ItemActionCallback.unpack(self.buttons()[0].callback_data)
        self.assertEqual(confirm.page, 2)
        self.assertEqual(
            ItemDetailsCallback.unpack(self.buttons()[1].callback_data).page, 2
        )
        await process_item_action(
            self.callback, confirm, self.session, self.user, self.state
        )
        self.assertIn("Страница 2 из 2", self.message.answer.call_args.args[0])
        self.assertEqual(
            [d.item_id for d in self.item_callbacks()],
            [item.id for item in self.items[10:20]],
        )
        self.assertTrue(
            all(d.page == 1 and d.status == "planned" for d in self.item_callbacks())
        )

    async def test_page_query_never_exposes_foreign_category(self):
        items, page, pages = await ORMQueryItem(
            self.session, self.category.id, user_id=999
        ).get_items_page(2)
        self.assertEqual((items, page, pages), ([], 0, 1))

    def test_legacy_callbacks_default_to_first_page_and_payloads_fit_limit(self):
        for callback_type, legacy in (
            (ItemListCallback, "items:1:planned"),
            (ItemDetailsCallback, "item:1:2:planned"),
            (ItemActionCallback, "ia:1:2:planned:confirm_delete"),
            (ItemEditFieldCallback, "if:1:2:planned:image_url"),
            (ItemSetStatusCallback, "is:1:2:planned:completed"),
        ):
            with self.subTest(callback_type=callback_type):
                data = callback_type.unpack(legacy)
                self.assertEqual(data.page, 0)
                self.assertEqual(callback_type.unpack(data.pack()), data)
                data.category_id = 2_147_483_647
                if hasattr(data, "item_id"):
                    data.item_id = 2_147_483_647
                data.page = 2_147_483_647
                self.assertLessEqual(len(data.pack().encode()), 64)
        for page in (-1, 2_147_483_648):
            with self.assertRaises(ValueError):
                ItemListCallback(category_id=1, page=page)


if __name__ == "__main__":
    unittest.main()
