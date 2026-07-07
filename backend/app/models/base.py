from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Declarative base shared by all models; its metadata is the Alembic autogenerate target."""

class UUIDPkMixin:
    """Server-generated UUID primary key (Postgres >=13 built-in gen_random_uuid(), no extension needed)."""
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

class TimestampMixin:
    """UTC timestamps; created_at is set once, updated_at refreshes on every ORM-issued UPDATE."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
