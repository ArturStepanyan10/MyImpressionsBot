from aiogram.fsm.state import State, StatesGroup

 
class FSMFillFormCategoryState(StatesGroup):
    """
    Класс для состояния бота. Тут перечислены состояния ожидания
    и в данных состояних будет находится БОТ
    """

    fill_category_id = State()  # Состояние ожидания выбора категории для изменения или удаления
    fill_add_title = State()  # Состояние ожидания ввода названия категории
    fill_update_title = State()  # Состояние ожидания ввода нового названия категории