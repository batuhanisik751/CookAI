import uuid
from unittest.mock import patch

import pytest

from app.models.job import ProcessingJob
from app.models.recipe import Ingredient, Recipe, Step
from app.models.substitution import IngredientSubstitution
from app.models.user_profile import UserProfile
from app.schemas.substitution import LLMSubstitutionItem
from app.services.substitution_engine import SubstitutionResult

TIKTOK_URL = "https://www.tiktok.com/@user/video/123"


@pytest.fixture
async def recipe_in_db(async_db_session):
    """Create a complete job + recipe with ingredients and steps."""
    job_id = uuid.uuid4()
    job = ProcessingJob(
        id=job_id,
        source_url=TIKTOK_URL,
        normalized_url=TIKTOK_URL,
        platform="tiktok",
        status="complete",
    )
    async_db_session.add(job)
    await async_db_session.flush()

    recipe_id = uuid.uuid4()
    recipe = Recipe(
        id=recipe_id,
        job_id=job_id,
        source_url=TIKTOK_URL,
        platform="tiktok",
        title="Butter Cookies",
        servings=24,
        difficulty="easy",
        cuisine_tags=["American"],
        confidence={
            "title": "high",
            "servings": "high",
            "prep_time": "high",
            "cook_time": "high",
            "ingredients": "high",
            "steps": "high",
            "overall": "high",
        },
    )
    async_db_session.add(recipe)
    await async_db_session.flush()

    butter = Ingredient(
        recipe_id=recipe_id,
        name="butter",
        quantity="1",
        unit="cup",
        order_index=0,
        confidence="high",
    )
    flour = Ingredient(
        recipe_id=recipe_id,
        name="flour",
        quantity="2",
        unit="cups",
        order_index=1,
        confidence="high",
    )
    eggs = Ingredient(
        recipe_id=recipe_id,
        name="eggs",
        quantity="2",
        unit=None,
        order_index=2,
        confidence="high",
    )
    async_db_session.add_all([butter, flour, eggs])
    await async_db_session.flush()

    step = Step(
        recipe_id=recipe_id,
        step_number=1,
        instruction="Cream butter, add flour and eggs, bake.",
        confidence="high",
    )
    async_db_session.add(step)
    await async_db_session.commit()

    return {
        "recipe_id": recipe_id,
        "ingredient_ids": {
            "butter": butter.id,
            "flour": flour.id,
            "eggs": eggs.id,
        },
    }


@pytest.fixture
async def recipe_with_subs(async_db_session, recipe_in_db):
    """Recipe that already has substitutions persisted."""
    ids = recipe_in_db["ingredient_ids"]
    rid = recipe_in_db["recipe_id"]

    sub = IngredientSubstitution(
        ingredient_id=ids["butter"],
        recipe_id=rid,
        substitute_name="coconut oil",
        ratio_explanation="1:1",
        dietary_tags=["dairy-free"],
        impact_notes="Slight coconut flavor",
        confidence="high",
        source="knowledge_base",
    )
    async_db_session.add(sub)
    await async_db_session.commit()
    return recipe_in_db


@pytest.fixture
async def profile_in_db(async_db_session):
    profile = UserProfile(
        display_name="Test User",
        dietary_restrictions=["dairy-free"],
        allergies=[],
        disliked_ingredients=[],
    )
    async_db_session.add(profile)
    await async_db_session.commit()
    await async_db_session.refresh(profile)
    return profile.id


SAMPLE_LLM_RESPONSE = {
    "substitutions": [
        {
            "original_ingredient": "butter",
            "role_in_recipe": "fat",
            "substitutions": [
                {
                    "substitute_name": "vegan butter",
                    "substitute_quantity": "1",
                    "substitute_unit": "cup",
                    "ratio_explanation": "Direct 1:1 swap",
                    "dietary_tags": ["vegan", "dairy-free"],
                    "impact_notes": "Very similar result",
                    "confidence": "high",
                },
            ],
        },
        {
            "original_ingredient": "flour",
            "role_in_recipe": "structural",
            "substitutions": [
                {
                    "substitute_name": "almond flour",
                    "substitute_quantity": "2",
                    "substitute_unit": "cups",
                    "ratio_explanation": "1:1",
                    "dietary_tags": ["gluten-free"],
                    "impact_notes": "Denser texture",
                    "confidence": "medium",
                },
            ],
        },
        {
            "original_ingredient": "eggs",
            "role_in_recipe": "binding",
            "substitutions": [
                {
                    "substitute_name": "flax eggs",
                    "substitute_quantity": "2",
                    "substitute_unit": "tbsp",
                    "ratio_explanation": "1 tbsp flax + 3 tbsp water per egg",
                    "dietary_tags": ["vegan", "egg-free"],
                    "impact_notes": "Less rise",
                    "confidence": "medium",
                },
            ],
        },
    ]
}


class TestGetRecipeSubstitutions:
    @pytest.mark.asyncio
    async def test_get_substitutions_empty(self, client, recipe_in_db):
        rid = recipe_in_db["recipe_id"]
        response = await client.get(f"/api/recipes/{rid}/substitutions")
        assert response.status_code == 200
        data = response.json()
        assert data["recipe_title"] == "Butter Cookies"
        assert len(data["ingredients"]) == 3
        # No substitutions generated yet
        assert all(len(i["substitutions"]) == 0 for i in data["ingredients"])

    @pytest.mark.asyncio
    async def test_get_substitutions_with_existing(self, client, recipe_with_subs):
        rid = recipe_with_subs["recipe_id"]
        response = await client.get(f"/api/recipes/{rid}/substitutions")
        assert response.status_code == 200
        data = response.json()

        butter_ing = next(i for i in data["ingredients"] if i["name"] == "butter")
        assert len(butter_ing["substitutions"]) == 1
        assert butter_ing["substitutions"][0]["substitute_name"] == "coconut oil"

    @pytest.mark.asyncio
    async def test_get_substitutions_recipe_not_found(self, client):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/recipes/{fake_id}/substitutions")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_substitutions_with_user_profile(
        self, client, recipe_in_db, profile_in_db
    ):
        rid = recipe_in_db["recipe_id"]
        response = await client.get(
            f"/api/recipes/{rid}/substitutions?user_profile_id={profile_in_db}"
        )
        assert response.status_code == 200
        data = response.json()

        butter_ing = next(i for i in data["ingredients"] if i["name"] == "butter")
        assert butter_ing["conflicts_with_preferences"] is True
        assert len(butter_ing["conflict_reasons"]) > 0

        # flour should not conflict with dairy-free
        flour_ing = next(i for i in data["ingredients"] if i["name"] == "flour")
        assert flour_ing["conflicts_with_preferences"] is False


class TestGenerateSubstitutions:
    @pytest.mark.asyncio
    async def test_generate_success(self, client, recipe_in_db):
        rid = recipe_in_db["recipe_id"]

        with patch("app.api.substitutions.generate_substitutions") as mock_gen:
            items = [
                LLMSubstitutionItem(**s) for s in SAMPLE_LLM_RESPONSE["substitutions"]
            ]
            mock_gen.return_value = SubstitutionResult(substitutions=items)

            response = await client.post(
                f"/api/recipes/{rid}/substitutions/generate",
                json={},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["recipe_title"] == "Butter Cookies"

        butter_ing = next(i for i in data["ingredients"] if i["name"] == "butter")
        assert len(butter_ing["substitutions"]) >= 1

    @pytest.mark.asyncio
    async def test_generate_recipe_not_found(self, client):
        fake_id = uuid.uuid4()
        response = await client.post(
            f"/api/recipes/{fake_id}/substitutions/generate",
            json={},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_persists_to_db(
        self, client, recipe_in_db, async_db_session
    ):
        rid = recipe_in_db["recipe_id"]

        with patch("app.api.substitutions.generate_substitutions") as mock_gen:
            items = [
                LLMSubstitutionItem(**s) for s in SAMPLE_LLM_RESPONSE["substitutions"]
            ]
            mock_gen.return_value = SubstitutionResult(substitutions=items)

            response = await client.post(
                f"/api/recipes/{rid}/substitutions/generate",
                json={},
            )

        assert response.status_code == 200

        # Verify data was persisted
        data = response.json()
        total_subs = sum(len(i["substitutions"]) for i in data["ingredients"])
        assert total_subs >= 3

    @pytest.mark.asyncio
    async def test_generate_with_dietary_filters(self, client, recipe_in_db):
        rid = recipe_in_db["recipe_id"]

        with patch("app.api.substitutions.generate_substitutions") as mock_gen:
            items = [
                LLMSubstitutionItem(**s) for s in SAMPLE_LLM_RESPONSE["substitutions"]
            ]
            mock_gen.return_value = SubstitutionResult(substitutions=items)

            response = await client.post(
                f"/api/recipes/{rid}/substitutions/generate",
                json={"dietary_filters": ["vegan"]},
            )

        assert response.status_code == 200
        # Verify the engine was called with dietary_filters
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        assert call_kwargs.kwargs.get("dietary_filters") == ["vegan"]
