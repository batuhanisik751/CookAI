import uuid
from datetime import datetime

from pydantic import BaseModel

# --- LLM output parsing (internal) ---


class LLMSubstitutionSuggestion(BaseModel):
    substitute_name: str
    substitute_quantity: str | None = None
    substitute_unit: str | None = None
    ratio_explanation: str | None = None
    dietary_tags: list[str] = []
    impact_notes: str = ""
    confidence: str = "medium"


class LLMSubstitutionItem(BaseModel):
    original_ingredient: str
    role_in_recipe: str
    substitutions: list[LLMSubstitutionSuggestion]


class LLMSubstitutionOutput(BaseModel):
    """Schema for parsing Claude's substitution JSON response."""

    substitutions: list[LLMSubstitutionItem]


# --- API response schemas ---


class IngredientSubstitutionSchema(BaseModel):
    id: uuid.UUID
    substitute_name: str
    substitute_quantity: str | None = None
    substitute_unit: str | None = None
    ratio_explanation: str | None = None
    role_in_recipe: str | None = None
    dietary_tags: list[str] | None = None
    impact_notes: str | None = None
    confidence: str = "medium"
    source: str = "llm"

    model_config = {"from_attributes": True}


class IngredientWithSubstitutionsSchema(BaseModel):
    name: str
    quantity: str | None = None
    unit: str | None = None
    order_index: int
    notes: str | None = None
    confidence: str = "high"
    conflicts_with_preferences: bool = False
    conflict_reasons: list[str] = []
    substitutions: list[IngredientSubstitutionSchema] = []


class RecipeSubstitutionsResponse(BaseModel):
    recipe_id: uuid.UUID
    recipe_title: str
    ingredients: list[IngredientWithSubstitutionsSchema]


# --- Request schemas ---


class SubstitutionRequest(BaseModel):
    user_profile_id: uuid.UUID | None = None
    dietary_filters: list[str] | None = None


# --- User profile schemas ---


class UserProfileCreate(BaseModel):
    display_name: str | None = None
    dietary_restrictions: list[str] = []
    allergies: list[str] = []
    disliked_ingredients: list[str] = []


class UserProfileUpdate(BaseModel):
    display_name: str | None = None
    dietary_restrictions: list[str] | None = None
    allergies: list[str] | None = None
    disliked_ingredients: list[str] | None = None
    pantry_items: list[str] | None = None


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    display_name: str | None = None
    dietary_restrictions: list[str] = []
    allergies: list[str] = []
    disliked_ingredients: list[str] = []
    pantry_items: list[str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Pantry mode (stretch) ---


class PantryIngredientStatus(BaseModel):
    name: str
    quantity: str | None = None
    unit: str | None = None
    in_pantry: bool = False
    substitutions: list[IngredientSubstitutionSchema] = []


class PantryCheckResponse(BaseModel):
    recipe_id: uuid.UUID
    ingredients: list[PantryIngredientStatus]
    have_count: int
    missing_count: int
