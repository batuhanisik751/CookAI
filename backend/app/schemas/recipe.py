import uuid
from datetime import datetime

from pydantic import BaseModel


class IngredientSchema(BaseModel):
    name: str
    quantity: str | None = None
    unit: str | None = None
    order_index: int
    notes: str | None = None
    confidence: str = "high"


class StepSchema(BaseModel):
    step_number: int
    instruction: str
    duration_estimate: str | None = None
    tip: str | None = None
    confidence: str = "high"


class ConfidenceScores(BaseModel):
    title: str = "high"
    servings: str = "medium"
    prep_time: str = "medium"
    cook_time: str = "medium"
    ingredients: str = "high"
    steps: str = "high"
    overall: str = "high"


class RecipeResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    title: str
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    difficulty: str | None = None
    cuisine_tags: list[str] | None = None
    language: str | None = None
    ingredients: list[IngredientSchema]
    steps: list[StepSchema]
    confidence: ConfidenceScores | None = None
    needs_review: bool = False
    review_flags: list[str] | None = None
    source_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LLMRecipeOutput(BaseModel):
    """Internal schema for parsing Claude's structured JSON response."""

    title: str
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    difficulty: str | None = None
    cuisine_tags: list[str] = []
    ingredients: list[IngredientSchema]
    steps: list[StepSchema]
    confidence: ConfidenceScores
    review_flags: list[str] = []
