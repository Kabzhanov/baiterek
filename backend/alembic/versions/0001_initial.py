"""initial schema — SPEC.md §3.1 tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-07

Creates the eleven MVP tables (organizations, users, service_definitions,
applications, documents, dictionaries, notifications, analytics_materials,
map_projects, knowledge_items, audit_log) with the constraints mandated by
docs/IMPLEMENTATION_PLAN.md §6:

- `service_definitions`: unique (service_id, version) — versioned Definitions.
- `applications`: composite FK to (service_id, version); optimistic `revision`;
  partial unique index enforcing a single active draft per
  (user_id, service_id, service_version); status/user/service/updated_at indexes.
- All timestamps are `timestamptz`, defaulted to `now()` at the DB layer (UTC).
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

user_role = postgresql.ENUM("entrepreneur", "admin", "author", name="user_role", create_type=False)
service_status = postgresql.ENUM("draft", "published", "archived", name="service_status", create_type=False)
analytics_material_type = postgresql.ENUM("dashboard", "report", "financial", "research", name="analytics_material_type", create_type=False)
knowledge_item_category = postgresql.ENUM("guide", "template", "checklist", "calculator", "review", name="knowledge_item_category", create_type=False)

def _timestamp_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    ]

def upgrade() -> None:
    bind = op.get_bind()
    user_role.create(bind, checkfirst=True)
    service_status.create(bind, checkfirst=True)
    analytics_material_type.create(bind, checkfirst=True)
    knowledge_item_category.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(64), nullable=False),
        sa.Column("logo", sa.String(512)),
        sa.Column("color", sa.String(16)),
        sa.Column("site_url", sa.String(512)),
        *_timestamp_columns(),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("iin_bin", sa.String(12), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="entrepreneur"),
        sa.Column("profile", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamp_columns(),
        sa.UniqueConstraint("iin_bin", name="uq_users_iin_bin"),
    )
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "service_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("status", service_status, nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("definition", postgresql.JSONB, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *_timestamp_columns(),
        sa.UniqueConstraint("service_id", "version", name="uq_service_definitions_service_id_version"),
    )
    op.create_index("ix_service_definitions_org_id", "service_definitions", ["org_id"])
    op.create_index("ix_service_definitions_status", "service_definitions", ["status"])
    op.create_index("ix_service_definitions_slug", "service_definitions", ["slug"])
    op.create_index("ix_service_definitions_updated_at", "service_definitions", ["updated_at"])

    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("number", sa.String(32)),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(64), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("checkpoint", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("data", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("timeline", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_timestamp_columns(),
        sa.UniqueConstraint("number", name="uq_applications_number"),
        sa.ForeignKeyConstraint(
            ["service_id", "service_version"],
            ["service_definitions.service_id", "service_definitions.version"],
            ondelete="RESTRICT",
            name="fk_applications_service_definition",
        ),
    )
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_service_id", "applications", ["service_id"])
    op.create_index("ix_applications_updated_at", "applications", ["updated_at"])
    op.create_index(
        "uq_applications_active_draft",
        "applications",
        ["user_id", "service_id", "service_version"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(128), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("signed_by_ecp", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("signature_meta", postgresql.JSONB),
        *_timestamp_columns(),
    )
    op.create_index("ix_documents_application_id", "documents", ["application_id"])

    op.create_table(
        "dictionaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("items", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        *_timestamp_columns(),
        sa.UniqueConstraint("code", name="uq_dictionaries_code"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id", ondelete="CASCADE")),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        *_timestamp_columns(),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_application_id", "notifications", ["application_id"])

    op.create_table(
        "analytics_materials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", analytics_material_type, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("source", sa.String(255)),
        sa.Column("period", sa.String(64)),
        sa.Column("url", sa.String(512)),
        sa.Column("embed_allowed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        *_timestamp_columns(),
    )
    op.create_index("ix_analytics_materials_org_id", "analytics_materials", ["org_id"])
    op.create_index("ix_analytics_materials_type", "analytics_materials", ["type"])

    op.create_table(
        "map_projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region_code", sa.String(16), nullable=False),
        sa.Column("locality", sa.String(255)),
        sa.Column("lat", sa.Numeric(9, 6), nullable=False),
        sa.Column("lng", sa.Numeric(9, 6), nullable=False),
        sa.Column("industry", sa.String(128)),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("is_demo", sa.Boolean, nullable=False, server_default=sa.text("true")),
        *_timestamp_columns(),
    )
    op.create_index("ix_map_projects_org_id", "map_projects", ["org_id"])
    op.create_index("ix_map_projects_region_code", "map_projects", ["region_code"])
    op.create_index("ix_map_projects_status", "map_projects", ["status"])

    op.create_table(
        "knowledge_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("category", knowledge_item_category, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("content", sa.Text),
        sa.Column("url", sa.String(512)),
        *_timestamp_columns(),
    )
    op.create_index("ix_knowledge_items_category", "knowledge_items", ["category"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True)),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("knowledge_items")
    op.drop_table("map_projects")
    op.drop_table("analytics_materials")
    op.drop_table("notifications")
    op.drop_table("dictionaries")
    op.drop_table("documents")
    op.drop_table("applications")
    op.drop_table("service_definitions")
    op.drop_table("users")
    op.drop_table("organizations")

    bind = op.get_bind()
    knowledge_item_category.drop(bind, checkfirst=True)
    analytics_material_type.drop(bind, checkfirst=True)
    service_status.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)
