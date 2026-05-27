from aiogram.fsm.state import State, StatesGroup


class FSMFillFormCategoryState(StatesGroup):
    """
    Класс для состояния бота при работе с категориями.
    Тут перечислены состояния ожидания и в данных состояних будет находится БОТ.
    """

    fill_add_title = (
        State()
    )  # Состояние ожидания ввода названия категории для добавления
    fill_update_title = (
        State()
    )  # Состояние ожидания ввода нового названия категории для изменения
