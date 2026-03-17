import uuid

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Recipe(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "recipes"

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processing_jobs.id"), nullable=False, unique=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cuisine_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    caption_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)

    job: Mapped["ProcessingJob"] = relationship(  # noqa: F821
        back_populates="recipe"
    )
    ingredients: Mapped[list["Ingredient"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="Ingredient.order_index",
    )
    steps: Mapped[list["Step"]] = relationship(
        back_populates="recipe",
        cascade="all, delete-orphan",
        order_by="Step.step_number",
    )
    substitutions: Mapped[list["IngredientSubstitution"]] = relationship(  # noqa: F821
        back_populates="recipe",
        cascade="all, delete-orphan",
    )


class Ingredient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredients"

    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), default="high")

    recipe: Mapped["Recipe"] = relationship(back_populates="ingredients")
    substitutions: Mapped[list["IngredientSubstitution"]] = relationship(  # noqa: F821
        back_populates="ingredient",
        cascade="all, delete-orphan",
    )


class Step(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "steps"

    recipe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    duration_estimate: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tip: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(10), default="high")

    recipe: Mapped["Recipe"] = relationship(back_populates="steps")
