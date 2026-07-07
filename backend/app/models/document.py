from __future__ import annotations
import uuid
from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class Document(UUIDPkMixin, TimestampMixin, Base):
    """Файл, приложенный к заявке. `storage_path` — путь вне публичного web-каталога (SPEC §7)."""
    __tablename__ = "documents"

    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    field_key: Mapped[str] = mapped_column(String(128), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    signed_by_ecp: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    signature_meta: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index("ix_documents_application_id", "application_id"),)
