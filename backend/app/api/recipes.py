import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.recipe import Recipe
from app.schemas.error import ErrorResponse
from app.schemas.recipe import (
    ConfidenceScores,
    IngredientSchema,
    RecipeResponse,
    StepSchema,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.get(
    "/{recipe_id}",
    response_model=RecipeResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_recipe(
    recipe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> RecipeResponse:
    """Get the full extracted recipe with ingredients and steps."""
    result = await db.get(
        Recipe,
        recipe_id,
        options=[
            selectinload(Recipe.ingredients),
            selectinload(Recipe.steps),
        ],
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "RECIPE_NOT_FOUND",
                    "message": f"Recipe {recipe_id} not found.",
                }
            },
        )

    return RecipeResponse(
        id=result.id,
        job_id=result.job_id,
        title=result.title,
        servings=result.servings,
        prep_time_minutes=result.prep_time_minutes,
        cook_time_minutes=result.cook_time_minutes,
        difficulty=result.difficulty,
        cuisine_tags=result.cuisine_tags,
        language=result.language,
        ingredients=[
            IngredientSchema(
                name=i.name,
                quantity=i.quantity,
                unit=i.unit,
                order_index=i.order_index,
                notes=i.notes,
                confidence=i.confidence,
            )
            for i in result.ingredients
        ],
        steps=[
            StepSchema(
                step_number=s.step_number,
                instruction=s.instruction,
                duration_estimate=s.duration_estimate,
                tip=s.tip,
                confidence=s.confidence,
            )
            for s in result.steps
        ],
        confidence=ConfidenceScores(**result.confidence) if result.confidence else None,
        needs_review=result.needs_review,
        review_flags=result.review_flags,
        source_url=result.source_url,
        created_at=result.created_at,
    )
