from __future__ import annotations
import enum
import uuid
from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class AnalyticsMaterialType(str, enum.Enum):
    DASHBOARD = "dashboard"
    REPORT = "report"
    FINANCIAL = "financial"
    RESEARCH = "research"

class AnalyticsMaterial(UUIDPkMixin, TimestampMixin, Base):
    """Каталог модуля аналитической отчетности (SPEC §4.5)."""
    __tablename__ = "analytics_materials"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[AnalyticsMaterialType] = mapped_column(Enum(AnalyticsMaterialType, name="analytics_material_type", native_enum=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))
    period: Mapped[str | None] = mapped_column(String(64))
    url: Mapped[str | None] = mapped_column(String(512))
    embed_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        Index("ix_analytics_materials_org_id", "org_id"),
        Index("ix_analytics_materials_type", "type"),
    )
