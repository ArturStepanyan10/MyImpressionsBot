from aiogram.filters.callback_data import CallbackData

from app.core.enums import ItemStatus

ITEM_STATUS_FILTERS: dict[str, ItemStatus | None] = {
    "all": None,
    "planned": ItemStatus.PLANNED,
    "progress": ItemStatus.IN_PROGRESS,
    "completed": ItemStatus.COMPLETED,
}


class ItemListCallback(CallbackData, prefix="items"):
    category_id: int
    status: str = "all"


class ItemDetailsCallback(CallbackData, prefix="item"):
    category_id: int
    item_id: int
    status: str = "all"


class ItemActionCallback(ItemDetailsCallback, prefix="ia"):
    action: str


class ItemEditFieldCallback(ItemDetailsCallback, prefix="if"):
    field: str


class ItemSetStatusCallback(ItemDetailsCallback, prefix="is"):
    new_status: str
