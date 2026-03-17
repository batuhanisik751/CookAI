"""add processing_jobs table

Revision ID: 5bb4a483705c
Revises:
Create Date: 2026-03-17 14:09:03.419922

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5bb4a483705c"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "processing_jobs",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("media_dir", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_processing_jobs_normalized_url",
        "processing_jobs",
        ["normalized_url"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_normalized_url", table_name="processing_jobs")
    op.drop_table("processing_jobs")
