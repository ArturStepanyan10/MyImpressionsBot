import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from app.handlers.base_hndlrs import process_help_command, process_start_command
from app.keyboards.category_kb.basic_kb import all_category_keyboard
from app.keyboards.common_kb import common_btns
from app.states.forms_state import FSMEditItemState


class MainMenuTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.state = FSMContext(
            storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1)
        )
        self.message = SimpleNamespace(answer=AsyncMock())

    async def test_help_restores_category_menu_when_no_form_is_active(self):
        await process_help_command(self.message, self.state)
        self.assertEqual(
            self.message.answer.call_args.kwargs["reply_markup"], all_category_keyboard
        )

    async def test_help_keeps_active_form_and_cancel_button(self):
        await self.state.set_state(FSMEditItemState.fill_value)
        await self.state.set_data({"item_id": 5, "field": "title"})
        await process_help_command(self.message, self.state)
        self.assertEqual(
            self.message.answer.call_args.kwargs["reply_markup"], common_btns["cancel"]
        )
        self.assertEqual(
            await self.state.get_state(), FSMEditItemState.fill_value.state
        )
        self.assertEqual(await self.state.get_data(), {"item_id": 5, "field": "title"})

    async def test_start_clears_form_before_returning_to_category_menu(self):
        await self.state.set_state(FSMEditItemState.fill_value)
        await self.state.set_data({"item_id": 5, "field": "title"})
        await process_start_command(
            self.message, SimpleNamespace(name="User"), self.state
        )
        self.assertIsNone(await self.state.get_state())
        self.assertEqual(await self.state.get_data(), {})
        self.assertEqual(
            self.message.answer.call_args.kwargs["reply_markup"], all_category_keyboard
        )


if __name__ == "__main__":
    unittest.main()
