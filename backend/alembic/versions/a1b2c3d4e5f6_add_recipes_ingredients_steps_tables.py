"""add recipes ingredients steps tables

Revision ID: a1b2c3d4e5f6
Revises: 5bb4a483705c
Create Date: 2026-03-17 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5bb4a483705c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            sa.UUID(),
            sa.ForeignKey("processing_jobs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("prep_time_minutes", sa.Integer(), nullable=True),
        sa.Column("cook_time_minutes", sa.Integer(), nullable=True),
        sa.Column("difficulty", sa.String(20), nullable=True),
        sa.Column("cuisine_tags", postgresql.JSONB(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("raw_transcript", sa.Text(), nullable=True),
        sa.Column("cleaned_transcript", sa.Text(), nullable=True),
        sa.Column("visual_analysis", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", postgresql.JSONB(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("review_flags", postgresql.JSONB(), nullable=True),
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

    op.create_table(
        "ingredients",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "recipe_id",
            sa.UUID(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="high"),
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
    op.create_index("ix_ingredients_recipe_id", "ingredients", ["recipe_id"])

    op.create_table(
        "steps",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "recipe_id",
            sa.UUID(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("duration_estimate", sa.String(50), nullable=True),
        sa.Column("tip", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="high"),
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
    op.create_index("ix_steps_recipe_id", "steps", ["recipe_id"])


def downgrade() -> None:
    op.drop_index("ix_steps_recipe_id", table_name="steps")
    op.drop_table("steps")
    op.drop_index("ix_ingredients_recipe_id", table_name="ingredients")
    op.drop_table("ingredients")
    op.drop_table("recipes")
