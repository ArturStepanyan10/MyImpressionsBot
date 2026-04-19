from aiogram.fsm.state import State, StatesGroup


class FSMFillFormCategoryState(StatesGroup):
    """
    Класс для состояния бота. Тут перечислены состояния ожидания
    и в данных состояних будет находится БОТ
    """

    fill_title = State()  # Состояние ожидания ввода названия категории
