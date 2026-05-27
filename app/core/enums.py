from enum import Enum


class CategoryAction(str, Enum):
    """
    Перечисление доступных действий с категориями.
    """
    
    LIST = "list"
    UPDATE = "update"
    DELETE = "delete"
    

class ItemStatus(str, Enum):
    PLANNED = "ЗАПЛАНИРОВАНО"
    IN_PROGRESS = "В ПРОЦЕССЕ"
    COMPLETED = "ВЫПОЛНЕНО"
