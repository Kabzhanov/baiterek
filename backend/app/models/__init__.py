"""SQLAlchemy models (SPEC.md §3.1). Import everything here so `Base.metadata` is complete
for Alembic autogenerate — alembic/env.py imports only `app.models.Base`."""
from app.models.analytics_material import AnalyticsMaterial, AnalyticsMaterialType
from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.dictionary import Dictionary
from app.models.document import Document
from app.models.knowledge_item import KnowledgeItem, KnowledgeItemCategory
from app.models.map_project import MapProject
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.service_definition import ServiceDefinition, ServiceStatus
from app.models.user import User, UserRole

__all__ = [
    "AnalyticsMaterial",
    "AnalyticsMaterialType",
    "Application",
    "AuditLog",
    "Base",
    "Dictionary",
    "Document",
    "KnowledgeItem",
    "KnowledgeItemCategory",
    "MapProject",
    "Notification",
    "Organization",
    "ServiceDefinition",
    "ServiceStatus",
    "User",
    "UserRole",
]
