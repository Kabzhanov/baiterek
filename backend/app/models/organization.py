from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class Organization(UUIDPkMixin, TimestampMixin, Base):
    """Дочерняя организация Холдинга (Даму, БРК, КАФ, АКК, KazakhExport, Отбасы, КЖК, QIC) либо сам Холдинг."""
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(64), nullable=False)
    logo: Mapped[str | None] = mapped_column(String(512))
    color: Mapped[str | None] = mapped_column(String(16))
    site_url: Mapped[str | None] = mapped_column(String(512))
