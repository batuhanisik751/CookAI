import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.recipe import Ingredient, Recipe
from app.models.substitution import IngredientSubstitution
from app.models.user_profile import UserProfile
from app.schemas.error import ErrorResponse
from app.schemas.recipe import IngredientSchema, StepSchema
from app.schemas.substitution import (
    IngredientSubstitutionSchema,
    IngredientWithSubstitutionsSchema,
    RecipeSubstitutionsResponse,
    SubstitutionRequest,
)
from app.services.preference_matcher import check_ingredient_conflicts
from app.services.substitution_engine import SubstitutionError, generate_substitutions
from app.services.substitution_kb import lookup_bulk_substitutions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recipes", tags=["substitutions"])


async def _load_recipe_with_subs(db: AsyncSession, recipe_id: uuid.UUID) -> Recipe:
    """Load recipe with ingredients, steps, and substitutions."""
    stmt = (
        select(Recipe)
        .where(Recipe.id == recipe_id)
        .options(
            selectinload(Recipe.ingredients).selectinload(Ingredient.substitutions),
            selectinload(Recipe.steps),
        )
    )
    result = await db.execute(stmt)
    recipe = result.scalar_one_or_none()
    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "RECIPE_NOT_FOUND",
                    "message": f"Recipe {recipe_id} not found.",
                }
            },
        )
    return recipe


def _build_response(
    recipe: Recipe,
    conflicts: dict[str, list[str]] | None = None,
) -> RecipeSubstitutionsResponse:
    """Build the substitutions response from a loaded recipe."""
    conflicts = conflicts or {}

    ingredients = []
    for ing in recipe.ingredients:
        conflict_reasons = conflicts.get(ing.name, [])
        ingredients.append(
            IngredientWithSubstitutionsSchema(
                name=ing.name,
                quantity=ing.quantity,
                unit=ing.unit,
                order_index=ing.order_index,
                notes=ing.notes,
                confidence=ing.confidence,
                conflicts_with_preferences=bool(conflict_reasons),
                conflict_reasons=conflict_reasons,
                substitutions=[
                    IngredientSubstitutionSchema.model_validate(s)
                    for s in ing.substitutions
                ],
            )
        )

    return RecipeSubstitutionsResponse(
        recipe_id=recipe.id,
        recipe_title=recipe.title,
        ingredients=ingredients,
    )


async def _get_conflicts(
    db: AsyncSession,
    user_profile_id: uuid.UUID | None,
    ingredient_names: list[str],
) -> dict[str, list[str]]:
    """Load user profile and check for ingredient conflicts."""
    if not user_profile_id:
        return {}

    profile = await db.get(UserProfile, user_profile_id)
    if not profile:
        return {}

    return check_ingredient_conflicts(
        ingredient_names=ingredient_names,
        dietary_restrictions=profile.dietary_restrictions or [],
        allergies=profile.allergies or [],
        disliked_ingredients=profile.disliked_ingredients or [],
    )


@router.get(
    "/{recipe_id}/substitutions",
    response_model=RecipeSubstitutionsResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_recipe_substitutions(
    recipe_id: uuid.UUID,
    user_profile_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RecipeSubstitutionsResponse:
    """Get cached substitutions for a recipe's ingredients."""
    recipe = await _load_recipe_with_subs(db, recipe_id)

    conflicts = await _get_conflicts(
        db, user_profile_id, [i.name for i in recipe.ingredients]
    )

    return _build_response(recipe, conflicts)


@router.post(
    "/{recipe_id}/substitutions/generate",
    response_model=RecipeSubstitutionsResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def generate_recipe_substitutions(
    recipe_id: uuid.UUID,
    request: SubstitutionRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RecipeSubstitutionsResponse:
    """Generate substitutions for a recipe via knowledge base + LLM."""
    recipe = await _load_recipe_with_subs(db, recipe_id)

    # Build schema objects for the engine
    ingredient_schemas = [
        IngredientSchema(
            name=i.name,
            quantity=i.quantity,
            unit=i.unit,
            order_index=i.order_index,
            notes=i.notes,
            confidence=i.confidence,
        )
        for i in recipe.ingredients
    ]
    step_schemas = [
        StepSchema(
            step_number=s.step_number,
            instruction=s.instruction,
            duration_estimate=s.duration_estimate,
            tip=s.tip,
            confidence=s.confidence,
        )
        for s in recipe.steps
    ]

    # 1. Knowledge base lookup
    kb_results = await lookup_bulk_substitutions(
        db,
        [i.name for i in recipe.ingredients],
        categories=request.dietary_filters,
    )

    # 2. LLM generation
    try:
        llm_result = generate_substitutions(
            recipe_title=recipe.title,
            ingredients=ingredient_schemas,
            steps=step_schemas,
            dietary_filters=request.dietary_filters,
        )
    except SubstitutionError as e:
        logger.error("Substitution generation failed: %s", e.message)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": e.code,
                    "message": e.message,
                }
            },
        ) from e

    # 3. Clear existing substitutions and persist new ones
    for ing in recipe.ingredients:
        ing.substitutions.clear()
    await db.flush()

    # Build ingredient lookup by name
    ing_by_name: dict[str, Ingredient] = {i.name.lower(): i for i in recipe.ingredients}

    # Add KB results
    for ing_name, kb_entries in kb_results.items():
        ing = ing_by_name.get(ing_name.lower())
        if not ing:
            continue
        for entry in kb_entries:
            sub = IngredientSubstitution(
                ingredient_id=ing.id,
                recipe_id=recipe.id,
                substitute_name=entry.substitute_ingredient,
                ratio_explanation=entry.ratio,
                dietary_tags=[entry.category],
                impact_notes=entry.notes,
                confidence="high",
                source="knowledge_base",
            )
            db.add(sub)

    # Add LLM results
    for item in llm_result.substitutions:
        ing = ing_by_name.get(item.original_ingredient.lower())
        if not ing:
            continue
        for suggestion in item.substitutions:
            # Skip if already added from KB
            existing_names = {s.substitute_name.lower() for s in ing.substitutions}
            if suggestion.substitute_name.lower() in existing_names:
                continue

            sub = IngredientSubstitution(
                ingredient_id=ing.id,
                recipe_id=recipe.id,
                substitute_name=suggestion.substitute_name,
                substitute_quantity=suggestion.substitute_quantity,
                substitute_unit=suggestion.substitute_unit,
                ratio_explanation=suggestion.ratio_explanation,
                role_in_recipe=item.role_in_recipe,
                dietary_tags=suggestion.dietary_tags,
                impact_notes=suggestion.impact_notes,
                confidence=suggestion.confidence,
                source="llm",
            )
            db.add(sub)

    await db.commit()

    # Expire identity map so the reload fetches fresh substitutions from DB
    db.expire_all()

    # Reload to get all persisted substitutions
    recipe = await _load_recipe_with_subs(db, recipe_id)

    # 4. Apply preference matching
    conflicts = await _get_conflicts(
        db, request.user_profile_id, [i.name for i in recipe.ingredients]
    )

    return _build_response(recipe, conflicts)
