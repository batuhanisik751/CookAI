import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db
from app.models.recipe import Ingredient, Recipe
from app.models.user_profile import UserProfile
from app.schemas.error import ErrorResponse
from app.schemas.substitution import (
    IngredientSubstitutionSchema,
    PantryCheckResponse,
    PantryIngredientStatus,
    UserProfileCreate,
    UserProfileResponse,
    UserProfileUpdate,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post(
    "",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    body: UserProfileCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserProfileResponse:
    """Create a new user profile with dietary preferences."""
    profile = UserProfile(
        display_name=body.display_name,
        dietary_restrictions=body.dietary_restrictions,
        allergies=body.allergies,
        disliked_ingredients=body.disliked_ingredients,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return UserProfileResponse.model_validate(profile)


@router.get(
    "/{profile_id}",
    response_model=UserProfileResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserProfileResponse:
    """Get a user profile with dietary preferences."""
    profile = await db.get(UserProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROFILE_NOT_FOUND",
                    "message": f"Profile {profile_id} not found.",
                }
            },
        )
    return UserProfileResponse.model_validate(profile)


@router.patch(
    "/{profile_id}",
    response_model=UserProfileResponse,
    responses={404: {"model": ErrorResponse}},
)
async def update_profile(
    profile_id: uuid.UUID,
    body: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> UserProfileResponse:
    """Update dietary preferences on a user profile."""
    profile = await db.get(UserProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROFILE_NOT_FOUND",
                    "message": f"Profile {profile_id} not found.",
                }
            },
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)

    return UserProfileResponse.model_validate(profile)


@router.post(
    "/{profile_id}/pantry-check/{recipe_id}",
    response_model=PantryCheckResponse,
    responses={404: {"model": ErrorResponse}},
)
async def pantry_check(
    profile_id: uuid.UUID,
    recipe_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PantryCheckResponse:
    """Check which recipe ingredients the user has in their pantry."""
    profile = await db.get(UserProfile, profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "PROFILE_NOT_FOUND",
                    "message": f"Profile {profile_id} not found.",
                }
            },
        )

    recipe = await db.get(
        Recipe,
        recipe_id,
        options=[
            selectinload(Recipe.ingredients).selectinload(Ingredient.substitutions),
        ],
    )
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

    pantry = [item.lower() for item in (profile.pantry_items or [])]

    ingredients = []
    have_count = 0
    missing_count = 0

    for ing in recipe.ingredients:
        in_pantry = any(p in ing.name.lower() or ing.name.lower() in p for p in pantry)
        if in_pantry:
            have_count += 1
        else:
            missing_count += 1

        # Only include substitutions for missing items
        subs = []
        if not in_pantry:
            subs = [
                IngredientSubstitutionSchema.model_validate(s)
                for s in ing.substitutions
            ]

        ingredients.append(
            PantryIngredientStatus(
                name=ing.name,
                quantity=ing.quantity,
                unit=ing.unit,
                in_pantry=in_pantry,
                substitutions=subs,
            )
        )

    return PantryCheckResponse(
        recipe_id=recipe_id,
        ingredients=ingredients,
        have_count=have_count,
        missing_count=missing_count,
    )
