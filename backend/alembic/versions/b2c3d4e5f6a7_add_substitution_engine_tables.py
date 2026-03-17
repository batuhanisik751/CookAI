"""add substitution engine tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-17 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("dietary_restrictions", postgresql.JSONB(), nullable=True),
        sa.Column("allergies", postgresql.JSONB(), nullable=True),
        sa.Column("disliked_ingredients", postgresql.JSONB(), nullable=True),
        sa.Column("pantry_items", postgresql.JSONB(), nullable=True),
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
        "substitution_knowledge_base",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("original_ingredient", sa.Text(), nullable=False),
        sa.Column("substitute_ingredient", sa.Text(), nullable=False),
        sa.Column("ratio", sa.String(100), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("flavor_similarity", sa.String(10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_common_pantry", sa.Boolean(), nullable=False, server_default="false"
        ),
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
        "ix_skb_original_ingredient",
        "substitution_knowledge_base",
        ["original_ingredient"],
    )
    op.create_index(
        "ix_skb_original_category",
        "substitution_knowledge_base",
        ["original_ingredient", "category"],
    )

    op.create_table(
        "ingredient_substitutions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "ingredient_id",
            sa.UUID(),
            sa.ForeignKey("ingredients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recipe_id",
            sa.UUID(),
            sa.ForeignKey("recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("substitute_name", sa.Text(), nullable=False),
        sa.Column("substitute_quantity", sa.String(50), nullable=True),
        sa.Column("substitute_unit", sa.String(50), nullable=True),
        sa.Column("ratio_explanation", sa.Text(), nullable=True),
        sa.Column("role_in_recipe", sa.String(30), nullable=True),
        sa.Column("dietary_tags", postgresql.JSONB(), nullable=True),
        sa.Column("impact_notes", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("source", sa.String(20), nullable=False, server_default="llm"),
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
        sa.UniqueConstraint(
            "ingredient_id", "substitute_name", name="uq_ingredient_substitute"
        ),
    )
    op.create_index(
        "ix_is_ingredient_id", "ingredient_substitutions", ["ingredient_id"]
    )
    op.create_index("ix_is_recipe_id", "ingredient_substitutions", ["recipe_id"])


def downgrade() -> None:
    op.drop_index("ix_is_recipe_id", table_name="ingredient_substitutions")
    op.drop_index("ix_is_ingredient_id", table_name="ingredient_substitutions")
    op.drop_table("ingredient_substitutions")
    op.drop_index("ix_skb_original_category", table_name="substitution_knowledge_base")
    op.drop_index(
        "ix_skb_original_ingredient", table_name="substitution_knowledge_base"
    )
    op.drop_table("substitution_knowledge_base")
    op.drop_table("user_profiles")
