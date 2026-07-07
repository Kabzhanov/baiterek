"""applications.completed_stages — SPEC.md §4.3 «Многоэтапность»

Revision ID: 0002_completed_stages
Revises: 0001_initial
Create Date: 2026-07-08

Additive-only: adds a single nullable-never JSONB column with a `'[]'::jsonb` server
default (so the migration is safe against existing rows) that tracks which stage keys
of the current Service Definition an application has already submitted. Combined with
`applications.checkpoint.stage_key` (see app/api/screen.py), this is what lets a
multi-stage service (e.g. SPEC.md §9 service A: этап I → одобрение → этап II) gate
PATCH/submit per-stage instead of per-application (see app/api/applications.py
`_stage_open`).
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_completed_stages"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "applications",
        sa.Column(
            "completed_stages",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("applications", "completed_stages")
