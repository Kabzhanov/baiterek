from __future__ import annotations
from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class Dictionary(UUIDPkMixin, TimestampMixin, Base):
    """Справочник (КАТО, ОКЭД, виды скота, банки-партнеры и т.п.); `code` — стабильный ключ,
    на который ссылается Definition-поле через `field.dictionary` (см. schemas/definition.py)."""
    __tablename__ = "dictionaries"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
