from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class MapProject(UUIDPkMixin, TimestampMixin, Base):
    """Проект интерактивной карты (SPEC §4.6). `is_demo=true` по умолчанию — все сид-данные
    подписываются в UI как демонстрационные, реальные факты никогда не выдаём молча."""
    __tablename__ = "map_projects"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region_code: Mapped[str] = mapped_column(String(16), nullable=False)
    locality: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    lng: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(128))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        Index("ix_map_projects_org_id", "org_id"),
        Index("ix_map_projects_region_code", "region_code"),
        Index("ix_map_projects_status", "status"),
    )
