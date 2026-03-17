import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SubstitutionKnowledgeBase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "substitution_knowledge_base"
    __table_args__ = (
        Index("ix_skb_original_ingredient", "original_ingredient"),
        Index("ix_skb_original_category", "original_ingredient", "category"),
    )

    original_ingredient: Mapped[str] = mapped_column(Text, nullable=False)
    substitute_ingredient: Mapped[str] = mapped_column(Text, nullable=False)
    ratio: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    flavor_similarity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_common_pantry: Mapped[bool] = mapped_column(Boolean, default=False)


class IngredientSubstitution(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredient_substitutions"
    __table_args__ = (
        UniqueConstraint(
            "ingredient_id", "substitute_name", name="uq_ingredient_substitute"
        ),
        Index("ix_is_ingredient_id", "ingredient_id"),
        Index("ix_is_recipe_id", "recipe_id"),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    substitute_name: Mapped[str] = mapped_column(Text, nullable=False)
    substitute_quantity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    substitute_unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ratio_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_in_recipe: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dietary_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    impact_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), default="medium")
    source: Mapped[str] = mapped_column(String(20), default="llm")

    ingredient: Mapped["Ingredient"] = relationship(back_populates="substitutions")  # noqa: F821
    recipe: Mapped["Recipe"] = relationship(back_populates="substitutions")  # noqa: F821
