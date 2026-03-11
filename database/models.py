from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, SmallInteger, func, ForeignKey, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from database.mixins.TimeStampMixin import TimestampMixin


class Base(DeclarativeBase):
    pass


class Category(Base, TimestampMixin):
    __tablename__ = 'category'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), ondelete='CASCADE', nullable=False)


class Item(Base, TimestampMixin):
    __tablename__ = 'item'

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    review: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(SmallInteger, CheckConstraint("rating BETWEEN 1 AND 5"))
    image_url: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), ondelete='CASCADE', nullable=False)


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True,)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(255))
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
