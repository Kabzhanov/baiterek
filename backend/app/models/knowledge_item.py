from __future__ import annotations
import enum
from sqlalchemy import Enum, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPkMixin

class KnowledgeItemCategory(str, enum.Enum):
    GUIDE = "guide"
    TEMPLATE = "template"
    CHECKLIST = "checklist"
    CALCULATOR = "calculator"
    REVIEW = "review"

class KnowledgeItem(UUIDPkMixin, TimestampMixin, Base):
    """Инструменты и материалы для бизнеса (SPEC §4.7): база знаний, шаблоны, чек-листы, калькуляторы, обзоры."""
    __tablename__ = "knowledge_items"

    category: Mapped[KnowledgeItemCategory] = mapped_column(Enum(KnowledgeItemCategory, name="knowledge_item_category", native_enum=True, values_callable=lambda e: [x.value for x in e]), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(512))

    __table_args__ = (Index("ix_knowledge_items_category", "category"),)
