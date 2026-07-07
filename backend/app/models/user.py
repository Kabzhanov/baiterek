from __future__ import annotations
import enum
from sqlalchemy import Enum, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class UserRole(str, enum.Enum):
    ENTREPRENEUR = "entrepreneur"
    ADMIN = "admin"
    AUTHOR = "author"

class User(UUIDPkMixin, TimestampMixin, Base):
    """Пользователь портала; авторизация — mock eGov IDP (SPEC §8), см. profile для ФИО/наименования и связки с БИН/ИИН."""
    __tablename__ = "users"

    iin_bin: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role", native_enum=True, values_callable=lambda e: [x.value for x in e]), nullable=False, server_default=UserRole.ENTREPRENEUR.value)
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    __table_args__ = (Index("ix_users_role", "role"),)
