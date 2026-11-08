import unittest
from html import unescape
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendPhoto
from aiogram.types import CallbackQuery, Message
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.enums import ItemStatus
from app.database.models import Base, Category, Item, User
from app.handlers.base_hndlrs import process_cancel_command
from app.handlers.item_action_hndlrs import (
    process_item_action,
    process_item_edit_field,
    process_item_edit_value,
    process_item_set_status,
)
from app.handlers.item_hndlrs import (
    process_back_to_categories,
    process_category_items,
    process_filtered_category_items,
    process_item_details,
)
from app.handlers.item_hndlrs import (
    router as item_router,
)
from app.keyboards.item_kb.callbacks import (
    ItemActionCallback,
    ItemDetailsCallback,
    ItemEditFieldCallback,
    ItemListCallback,
    ItemSetStatusCallback,
)
from app.keyboards.item_kb.inline_kb import get_item_details_keyboard
from app.services.item_services import get_item_card_parts, send_item_card
from app.states.forms_state import FSMEditItemState


class PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


class ItemBrowsingTests(unittest.IsolatedAsyncioTestCase):
    """Проверяет обработчики с реальными SQL-запросами в изолированной SQLite."""

    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.session = AsyncMock(spec=AsyncSession)
        self.session.execute.side_effect = self.db.execute
        self.state = FSMContext(
            storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
        )
        self.user = User(name="Owner", last_name="", telegram_id=1, username="owner")
        other_user = User(name="Other", last_name="", telegram_id=2, username="other")
        self.db.add_all([self.user, other_user])
        self.db.flush()
        self.category = Category(title="Книги <новые>", user_id=self.user.id)
        self.other_category = Category(title="Чужая", user_id=other_user.id)
        self.empty_category = Category(title="Пустая", user_id=self.user.id)
        self.db.add_all([self.category, self.other_category, self.empty_category])
        self.db.flush()
        self.planned = self.make_item(self.category.id, "Книга <1>", ItemStatus.PLANNED)
        self.completed = self.make_item(
            self.category.id, "Книга 2", ItemStatus.COMPLETED
        )
        self.foreign = self.make_item(
            self.other_category.id, "Чужой элемент", ItemStatus.PLANNED
        )
        self.db.commit()
        self.message = SimpleNamespace(
            text=None, answer=AsyncMock(), answer_photo=AsyncMock()
        )
        self.callback = SimpleNamespace(
            data=f"list_category_{self.category.id}",
            answer=AsyncMock(),
            message=self.message,
        )

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def make_item(self, category_id, title, status):
        item = Item(
            category_id=category_id,
            title=title,
            review="Отзыв <b>не разметка</b> & впечатления",
            rating=4,
            image_url="https://example.com/image.jpg",
            status=status,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def list_buttons(self):
        keyboard = self.message.answer.call_args.kwargs["reply_markup"]
        return [button for row in keyboard.inline_keyboard for button in row]

    async def test_list_opens_owned_items_and_keeps_actions(self):
        await process_category_items(self.callback, self.session, self.user, self.state)
        buttons = self.list_buttons()
        items = [
            ItemDetailsCallback.unpack(b.callback_data)
            for b in buttons
            if b.callback_data.startswith("item:")
        ]
        self.assertEqual(
            [data.item_id for data in items], [self.planned.id, self.completed.id]
        )
        self.assertIn("4/5", buttons[0].text)
        self.assertIn(
            f"add_item_{self.category.id}", [b.callback_data for b in buttons]
        )
        self.assertIn("item_categories", [b.callback_data for b in buttons])
        self.assertIn("&lt;новые&gt;", self.message.answer.call_args.args[0])

    async def test_all_status_filters_and_empty_results(self):
        for status, expected in (
            ("all", [self.planned.id, self.completed.id]),
            ("planned", [self.planned.id]),
            ("progress", []),
            ("completed", [self.completed.id]),
        ):
            with self.subTest(status=status):
                await process_filtered_category_items(
                    self.callback,
                    ItemListCallback(category_id=self.category.id, status=status),
                    self.session,
                    self.user,
                    self.state,
                )
                buttons = self.list_buttons()
                data = [
                    ItemDetailsCallback.unpack(b.callback_data)
                    for b in buttons
                    if b.callback_data.startswith("item:")
                ]
                self.assertEqual([item.item_id for item in data], expected)
                self.assertTrue(all(item.status == status for item in data))
                self.assertEqual(sum(b.text.startswith("✓ ") for b in buttons), 1)
                if not expected:
                    self.assertIn(
                        "нет элементов", self.message.answer.call_args.args[0]
                    )

    async def test_empty_category_still_offers_add_and_filters(self):
        self.callback.data = f"list_category_{self.empty_category.id}"
        await process_category_items(self.callback, self.session, self.user, self.state)
        self.assertIn("пока нет элементов", self.message.answer.call_args.args[0])
        self.assertEqual(len(self.list_buttons()), 6)

    async def test_unavailable_items_never_show_card(self):
        for category_id, item_id in (
            (self.category.id, 99999),
            (self.category.id, self.foreign.id),
            (self.other_category.id, self.foreign.id),
        ):
            with self.subTest(category_id=category_id, item_id=item_id):
                await process_item_details(
                    self.callback,
                    ItemDetailsCallback(category_id=category_id, item_id=item_id),
                    self.session,
                    self.user,
                    self.state,
                )
                self.assertTrue(self.callback.answer.call_args.kwargs["show_alert"])
        self.message.answer.assert_not_awaited()
        self.message.answer_photo.assert_not_awaited()

    async def test_foreign_category_cannot_be_listed(self):
        await process_filtered_category_items(
            self.callback,
            ItemListCallback(category_id=self.other_category.id),
            self.session,
            self.user,
            self.state,
        )
        self.assertTrue(self.callback.answer.call_args.kwargs["show_alert"])
        self.message.answer.assert_not_awaited()

    async def test_invalid_filter_is_rejected(self):
        await process_filtered_category_items(
            self.callback,
            ItemListCallback(category_id=self.category.id, status="invalid"),
            self.session,
            self.user,
            self.state,
        )
        self.session.execute.assert_not_awaited()
        self.assertTrue(self.callback.answer.call_args.kwargs["show_alert"])

    async def test_card_shows_data_and_preserves_filter(self):
        await process_item_details(
            self.callback,
            ItemDetailsCallback(
                category_id=self.category.id, item_id=self.planned.id, status="planned"
            ),
            self.session,
            self.user,
            self.state,
        )
        self.message.answer_photo.assert_awaited_once_with(photo=self.planned.image_url)
        text = self.message.answer.call_args.args[0]
        self.assertIn("Книга &lt;1&gt;", text)
        self.assertIn("&lt;b&gt;не разметка&lt;/b&gt;", text)
        self.assertIn("4/5", text)
        self.assertIn(ItemStatus.PLANNED.value, text)
        self.assertIn(self.planned.created_at.strftime("%d.%m.%Y"), text)
        buttons = self.list_buttons()
        self.assertEqual(
            [b.text for b in buttons],
            ["Изменить", "Изменить статус", "Удалить", "Назад"],
        )
        back = ItemListCallback.unpack(buttons[-1].callback_data)
        self.assertEqual(back.category_id, self.category.id)
        self.assertEqual(back.status, "planned")

    async def test_failed_photo_falls_back_to_card_and_link(self):
        self.message.answer_photo.side_effect = TelegramBadRequest(
            method=SendPhoto(chat_id=1, photo=self.planned.image_url),
            message="wrong type of the web page content",
        )
        keyboard = get_item_details_keyboard(self.category.id, self.planned.id)
        await send_item_card(self.message, self.planned, keyboard)
        self.assertIn("Книга &lt;1&gt;", self.message.answer.await_args_list[0].args[0])
        self.assertIn(self.planned.image_url, self.message.answer.call_args.args[0])
        self.assertEqual(self.message.answer.call_args.kwargs["reply_markup"], keyboard)

    async def test_long_review_preserves_text_and_telegram_limits(self):
        self.planned.title = "😀" * 255
        self.planned.review = "😀<&>" * 3000
        parts = get_item_card_parts(self.planned)
        plain_parts = []
        for part in parts:
            parser = PlainTextParser()
            parser.feed(part)
            plain = "".join(parser.parts)
            self.assertLessEqual(len(plain.encode("utf-16-le")) // 2, 4096)
            plain_parts.append(plain)
        self.assertIn(self.planned.review, "".join(plain_parts))
        self.assertEqual(
            unescape(parts[-1]), self.planned.review[-len(unescape(parts[-1])) :]
        )

    async def test_back_to_categories_only_lists_owned_categories(self):
        await process_back_to_categories(
            self.callback, self.session, self.user, self.state
        )
        ids = [int(b.callback_data.rsplit("_", 1)[1]) for b in self.list_buttons()]
        self.assertEqual(set(ids), {self.category.id, self.empty_category.id})

    def item_context(self):
        return {
            "category_id": self.category.id,
            "item_id": self.planned.id,
            "status": "planned",
        }

    async def start_edit(self, field):
        await process_item_edit_field(
            self.callback,
            ItemEditFieldCallback(**self.item_context(), field=field),
            self.session,
            self.user,
            self.state,
        )

    async def test_edit_menu_has_all_fields_and_back_to_card(self):
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.item_context(), action="edit"),
            self.session,
            self.user,
            self.state,
        )
        self.assertIn("Книга &lt;1&gt;", self.message.answer.call_args.args[0])
        buttons = self.list_buttons()
        self.assertEqual(
            [ItemEditFieldCallback.unpack(b.callback_data).field for b in buttons[:-1]],
            ["title", "review", "rating", "image_url"],
        )
        back = ItemDetailsCallback.unpack(buttons[-1].callback_data)
        self.assertEqual(back.status, "planned")
        self.assertIsNone(await self.state.get_state())

    async def test_edit_each_field_updates_only_selected_value(self):
        for field, text, expected in (
            ("title", " Новое <название> ", "Новое <название>"),
            ("review", " Новый отзыв & впечатления ", "Новый отзыв & впечатления"),
            ("rating", " 5 ", 5),
            (
                "image_url",
                " https://example.com/new.png ",
                "https://example.com/new.png",
            ),
        ):
            with self.subTest(field=field):
                original = {
                    name: getattr(self.planned, name)
                    for name in ("title", "review", "rating", "image_url")
                }
                await self.start_edit(field)
                self.assertEqual(
                    await self.state.get_state(), FSMEditItemState.fill_value.state
                )
                data = await self.state.get_data()
                self.assertEqual(data["field"], field)
                self.assertEqual(data["category_id"], self.category.id)
                self.assertEqual(data["item_id"], self.planned.id)
                self.message.text = text
                await process_item_edit_value(
                    self.message, self.state, self.session, self.user
                )
                self.db.refresh(self.planned)
                original[field] = expected
                self.assertEqual(
                    {name: getattr(self.planned, name) for name in original}, original
                )
                self.assertIsNone(await self.state.get_state())
                self.assertEqual(await self.state.get_data(), {})
                back = ItemListCallback.unpack(self.list_buttons()[-1].callback_data)
                self.assertEqual(back.status, "planned")

    async def test_invalid_edit_values_keep_form_and_database_unchanged(self):
        for field, values in (
            ("title", [None, " ", "x" * 256]),
            ("review", [None, " \n "]),
            ("rating", [None, "0", "6", "1.5", "²", "1" * 5000]),
            ("image_url", [None, "example.com", "ftp://example.com/a", "https://[bad"]),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    await self.start_edit(field)
                    original = getattr(self.planned, field)
                    self.message.text = value
                    await process_item_edit_value(
                        self.message, self.state, self.session, self.user
                    )
                    self.db.refresh(self.planned)
                    self.assertEqual(getattr(self.planned, field), original)
                    self.assertEqual(
                        await self.state.get_state(), FSMEditItemState.fill_value.state
                    )

    async def test_cancel_every_edit_field_returns_to_unchanged_card(self):
        for field in ("title", "review", "rating", "image_url"):
            with self.subTest(field=field):
                original = getattr(self.planned, field)
                await self.start_edit(field)
                await process_cancel_command(
                    self.message, self.state, self.session, self.user
                )
                self.assertIsNone(await self.state.get_state())
                self.db.refresh(self.planned)
                self.assertEqual(getattr(self.planned, field), original)
                back = ItemListCallback.unpack(self.list_buttons()[-1].callback_data)
                self.assertEqual(back.status, "planned")

    async def test_navigation_exits_edit_and_preserves_filter(self):
        await self.start_edit("title")
        await process_filtered_category_items(
            self.callback,
            ItemListCallback(category_id=self.category.id, status="planned"),
            self.session,
            self.user,
            self.state,
        )
        self.assertIsNone(await self.state.get_state())
        self.assertEqual(await self.state.get_data(), {})
        self.assertEqual(self.planned.title, "Книга <1>")

    async def test_lost_edit_context_never_updates_item(self):
        await self.state.set_state(FSMEditItemState.fill_value)
        self.message.text = "New"
        await process_item_edit_value(self.message, self.state, self.session, self.user)
        self.assertIsNone(await self.state.get_state())
        self.session.execute.assert_not_awaited()

    async def test_deleted_item_during_edit_is_handled(self):
        await self.start_edit("title")
        self.db.delete(self.planned)
        self.db.flush()
        self.message.text = "New"
        await process_item_edit_value(self.message, self.state, self.session, self.user)
        self.assertIsNone(await self.state.get_state())
        self.assertIn("больше недоступен", self.message.answer.call_args.args[0])

    async def test_status_menu_and_each_status_update(self):
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.item_context(), action="status"),
            self.session,
            self.user,
            self.state,
        )
        buttons = self.list_buttons()
        self.assertEqual(len(buttons), 4)
        self.assertTrue(buttons[0].text.startswith("✓ "))
        self.assertEqual(
            [
                ItemSetStatusCallback.unpack(b.callback_data).new_status
                for b in buttons[:-1]
            ],
            ["planned", "progress", "completed"],
        )
        for key, status in (
            ("progress", ItemStatus.IN_PROGRESS),
            ("completed", ItemStatus.COMPLETED),
            ("planned", ItemStatus.PLANNED),
        ):
            with self.subTest(status=status):
                await process_item_set_status(
                    self.callback,
                    ItemSetStatusCallback(**self.item_context(), new_status=key),
                    self.session,
                    self.user,
                    self.state,
                )
                self.db.refresh(self.planned)
                self.assertIs(self.planned.status, status)
                self.assertIsNone(await self.state.get_state())
                self.assertIn(status.value, self.message.answer.call_args.args[0])
                back = ItemListCallback.unpack(self.list_buttons()[-1].callback_data)
                self.assertEqual(back.status, "planned")

    async def test_delete_requires_confirmation_and_cancel_returns_to_card(self):
        item_id = self.planned.id
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.item_context(), action="delete"),
            self.session,
            self.user,
            self.state,
        )
        self.assertIsNotNone(self.db.get(Item, item_id))
        buttons = self.list_buttons()
        self.assertEqual([b.text for b in buttons], ["Да, удалить", "Нет, вернуться"])
        confirm = ItemActionCallback.unpack(buttons[0].callback_data)
        back = ItemDetailsCallback.unpack(buttons[1].callback_data)
        await process_item_details(
            self.callback, back, self.session, self.user, self.state
        )
        self.assertIsNotNone(self.db.get(Item, item_id))
        await process_item_action(
            self.callback, confirm, self.session, self.user, self.state
        )
        self.assertIsNone(self.db.get(Item, item_id))
        self.assertIsNotNone(self.db.get(Item, self.completed.id))
        self.assertIsNotNone(self.db.get(Item, self.foreign.id))
        self.assertIn("нет элементов", self.message.answer.call_args.args[0])
        self.assertTrue(any(b.text == "✓ Запланировано" for b in self.list_buttons()))
        self.message.answer.reset_mock()
        await process_item_action(
            self.callback, confirm, self.session, self.user, self.state
        )
        self.assertTrue(self.callback.answer.call_args.kwargs["show_alert"])
        self.message.answer.assert_not_awaited()

    async def test_card_actions_reject_foreign_items(self):
        context = {"category_id": self.other_category.id, "item_id": self.foreign.id}
        for action in ("edit", "status", "delete", "confirm_delete"):
            with self.subTest(action=action):
                await process_item_action(
                    self.callback,
                    ItemActionCallback(**context, action=action),
                    self.session,
                    self.user,
                    self.state,
                )
                self.assertTrue(self.callback.answer.call_args.kwargs["show_alert"])
        await process_item_edit_field(
            self.callback,
            ItemEditFieldCallback(**context, field="title"),
            self.session,
            self.user,
            self.state,
        )
        await process_item_set_status(
            self.callback,
            ItemSetStatusCallback(**context, new_status="completed"),
            self.session,
            self.user,
            self.state,
        )
        self.assertIsNotNone(self.db.get(Item, self.foreign.id))
        self.assertIs(self.foreign.status, ItemStatus.PLANNED)
        self.assertIsNone(await self.state.get_state())
        self.message.answer.assert_not_awaited()

    async def test_invalid_actions_never_start_forms_or_mutate_database(self):
        await process_item_action(
            self.callback,
            ItemActionCallback(**self.item_context(), action="unknown"),
            self.session,
            self.user,
            self.state,
        )
        await process_item_edit_field(
            self.callback,
            ItemEditFieldCallback(**self.item_context(), field="category_id"),
            self.session,
            self.user,
            self.state,
        )
        await process_item_set_status(
            self.callback,
            ItemSetStatusCallback(**self.item_context(), new_status="all"),
            self.session,
            self.user,
            self.state,
        )
        self.session.execute.assert_not_awaited()
        self.assertIsNone(await self.state.get_state())

    async def test_router_dispatches_edit_status_and_delete_from_callbacks(self):
        bot = AsyncMock(spec=Bot)
        user = {"id": 1, "is_bot": False, "first_name": "Owner"}
        message_data = {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 1, "type": "private"},
            "from": user,
        }

        async def click(data):
            callback = CallbackQuery.model_validate(
                {
                    "id": "test",
                    "from": user,
                    "chat_instance": "test",
                    "data": data.pack(),
                    "message": message_data,
                },
                context={"bot": bot},
            )
            await item_router.propagate_event(
                update_type="callback_query",
                event=callback,
                session=self.session,
                db_user=self.user,
                state=self.state,
                raw_state=await self.state.get_state(),
            )

        await click(ItemActionCallback(**self.item_context(), action="edit"))
        self.assertGreater(bot.await_count, 0)
        await click(ItemEditFieldCallback(**self.item_context(), field="title"))
        self.assertEqual(
            await self.state.get_state(), FSMEditItemState.fill_value.state
        )
        message = Message.model_validate(
            {**message_data, "text": "Changed via router"}, context={"bot": bot}
        )
        await item_router.propagate_event(
            update_type="message",
            event=message,
            session=self.session,
            db_user=self.user,
            state=self.state,
            raw_state=await self.state.get_state(),
        )
        self.db.refresh(self.planned)
        self.assertEqual(self.planned.title, "Changed via router")
        await click(
            ItemSetStatusCallback(**self.item_context(), new_status="completed")
        )
        self.db.refresh(self.planned)
        self.assertIs(self.planned.status, ItemStatus.COMPLETED)
        item_id = self.planned.id
        await click(ItemActionCallback(**self.item_context(), action="delete"))
        self.assertIsNotNone(self.db.get(Item, item_id))
        await click(ItemActionCallback(**self.item_context(), action="confirm_delete"))
        self.assertIsNone(self.db.get(Item, item_id))


if __name__ == "__main__":
    unittest.main()
