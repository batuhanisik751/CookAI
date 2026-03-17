import uuid

import pytest

from app.models.job import ProcessingJob
from app.models.recipe import Ingredient, Recipe, Step

TIKTOK_URL = "https://www.tiktok.com/@user/video/123"


class TestGetRecipe:
    @pytest.fixture
    async def recipe_in_db(self, async_db_session):
        """Create a complete job + recipe in the test database."""
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
            title="Classic Pancakes",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=15,
            difficulty="easy",
            cuisine_tags=["American", "Breakfast"],
            language="en",
            confidence={
                "title": "high",
                "servings": "medium",
                "prep_time": "medium",
                "cook_time": "medium",
                "ingredients": "high",
                "steps": "high",
                "overall": "high",
            },
            needs_review=False,
            review_flags=[],
        )
        async_db_session.add(recipe)
        await async_db_session.flush()

        async_db_session.add(
            Ingredient(
                recipe_id=recipe_id,
                name="flour",
                quantity="2",
                unit="cups",
                order_index=0,
                confidence="high",
            )
        )
        async_db_session.add(
            Ingredient(
                recipe_id=recipe_id,
                name="eggs",
                quantity="2",
                unit=None,
                order_index=1,
                confidence="high",
            )
        )
        async_db_session.add(
            Step(
                recipe_id=recipe_id,
                step_number=1,
                instruction="Mix flour and eggs.",
                confidence="high",
            )
        )
        async_db_session.add(
            Step(
                recipe_id=recipe_id,
                step_number=2,
                instruction="Cook on griddle.",
                confidence="high",
            )
        )
        await async_db_session.commit()

        return recipe_id

    @pytest.mark.asyncio
    async def test_get_recipe_success(self, client, recipe_in_db):
        response = await client.get(f"/api/recipes/{recipe_in_db}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Classic Pancakes"
        assert data["servings"] == 4
        assert data["difficulty"] == "easy"

    @pytest.mark.asyncio
    async def test_get_recipe_not_found(self, client):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/recipes/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "RECIPE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_recipe_includes_ingredients_and_steps(
        self, client, recipe_in_db
    ):
        response = await client.get(f"/api/recipes/{recipe_in_db}")
        assert response.status_code == 200
        data = response.json()

        assert len(data["ingredients"]) == 2
        assert data["ingredients"][0]["name"] == "flour"
        assert data["ingredients"][0]["quantity"] == "2"
        assert data["ingredients"][1]["name"] == "eggs"

        assert len(data["steps"]) == 2
        assert data["steps"][0]["step_number"] == 1
        assert data["steps"][0]["instruction"] == "Mix flour and eggs."
        assert data["steps"][1]["step_number"] == 2

    @pytest.mark.asyncio
    async def test_get_recipe_includes_confidence(self, client, recipe_in_db):
        response = await client.get(f"/api/recipes/{recipe_in_db}")
        data = response.json()
        assert data["confidence"]["overall"] == "high"
        assert data["needs_review"] is False

    @pytest.mark.asyncio
    async def test_get_recipe_includes_metadata(self, client, recipe_in_db):
        response = await client.get(f"/api/recipes/{recipe_in_db}")
        data = response.json()
        assert data["source_url"] == TIKTOK_URL
        assert data["language"] == "en"
        assert "American" in data["cuisine_tags"]
