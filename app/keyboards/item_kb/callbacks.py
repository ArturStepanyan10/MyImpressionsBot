from typing import Self

from aiogram.filters.callback_data import CallbackData
from pydantic import Field

from app.core.enums import ItemStatus

ITEM_STATUS_FILTERS: dict[str, ItemStatus | None] = {
    "all": None,
    "planned": ItemStatus.PLANNED,
    "progress": ItemStatus.IN_PROGRESS,
    "completed": ItemStatus.COMPLETED,
}


class ItemPaginationCallback(CallbackData, prefix="pagination"):
    """Принимает также кнопки, отправленные до появления номера страницы."""

    @classmethod
    def unpack(cls, value: str) -> Self:
        prefix, *parts = value.split(cls.__separator__)
        fields = list(cls.model_fields)
        if (
            prefix == cls.__prefix__
            and "page" in fields
            and len(parts) == len(fields) - 1
        ):
            parts.insert(fields.index("page"), "0")
            value = cls.__separator__.join([prefix, *parts])
        return super().unpack(value)


class ItemListCallback(ItemPaginationCallback, prefix="items"):
    category_id: int
    status: str = "all"
    page: int = Field(default=0, ge=0, le=2_147_483_647)


class ItemDetailsCallback(ItemPaginationCallback, prefix="item"):
    category_id: int
    item_id: int
    status: str = "all"
    page: int = Field(default=0, ge=0, le=2_147_483_647)


class ItemActionCallback(ItemDetailsCallback, prefix="ia"):
    action: str


class ItemEditFieldCallback(ItemDetailsCallback, prefix="if"):
    field: str


class ItemSetStatusCallback(ItemDetailsCallback, prefix="is"):
    new_status: str
