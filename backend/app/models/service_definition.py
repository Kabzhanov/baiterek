from __future__ import annotations
import enum
import uuid
from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class ServiceStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class ServiceDefinition(UUIDPkMixin, TimestampMixin, Base):
    """Ядро системы: версия декларативного описания услуги (SPEC §3.2 DSL).

    `id` — первичный ключ строки-версии; `service_id` — стабильный идентификатор
    услуги, общий для всех её версий (publish создаёт новую строку с version+1,
    предыдущие версии не изменяются — applications ссылаются на конкретную пару
    service_id+version через составной FK).
    """
    __tablename__ = "service_definitions"

    service_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, server_default=text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ServiceStatus] = mapped_column(Enum(ServiceStatus, name="service_status", native_enum=True, values_callable=lambda e: [x.value for x in e]), nullable=False, server_default=ServiceStatus.DRAFT.value)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("service_id", "version", name="uq_service_definitions_service_id_version"),
        Index("ix_service_definitions_org_id", "org_id"),
        Index("ix_service_definitions_status", "status"),
        Index("ix_service_definitions_slug", "slug"),
        Index("ix_service_definitions_updated_at", "updated_at"),
    )
