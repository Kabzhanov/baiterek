from __future__ import annotations
import uuid
from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class Application(UUIDPkMixin, TimestampMixin, Base):
    """Заявка на услугу (SPEC §3.1 + "Обязательное расширение" — checkpoint-модель).

    `status` намеренно НЕ нативный Postgres enum: набор статусов объявляется в
    самом Service Definition (`statuses.flow`, см. schemas/definition.py) и может
    отличаться между услугами — движок (app/engine) валидирует переходы, таблица
    лишь хранит текущее строковое значение.

    `revision` — optimistic-concurrency счётчик для PATCH .../draft (SPEC §2 "Автосохранение
    непрерывное"): каждый PATCH несёт `expected_revision`, устаревший запрос не может
    затереть более новое значение (обрабатывается в app/api, не на уровне БД).

    `checkpoint` = {"stage_key": ..., "step_key": ..., "screen_key": ...} — адресует экран
    по ключу первого поля, а не по индексу (динамическое дробление 3–6 и правила видимости
    не должны "уносить" сохранённую позицию).
    """
    __tablename__ = "applications"

    number: Mapped[str | None] = mapped_column(String(32), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    service_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    checkpoint: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    timeline: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))

    __table_args__ = (
        ForeignKeyConstraint(
            ["service_id", "service_version"],
            ["service_definitions.service_id", "service_definitions.version"],
            ondelete="RESTRICT",
            name="fk_applications_service_definition",
        ),
        # Один активный черновик на пользователь+услуга+версию (SPEC §2 "Модель данных").
        Index(
            "uq_applications_active_draft",
            "user_id", "service_id", "service_version",
            unique=True,
            postgresql_where=text("status = 'draft'"),
        ),
        Index("ix_applications_status", "status"),
        Index("ix_applications_user_id", "user_id"),
        Index("ix_applications_service_id", "service_id"),
        Index("ix_applications_updated_at", "updated_at"),
    )
