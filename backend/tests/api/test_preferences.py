import uuid

import pytest

from app.models.job import ProcessingJob
from app.models.recipe import Ingredient, Recipe, Step
from app.models.substitution import IngredientSubstitution
from app.models.user_profile import UserProfile


class TestCreateProfile:
    @pytest.mark.asyncio
    async def test_create_profile(self, client):
        response = await client.post(
            "/api/profiles",
            json={
                "display_name": "Test User",
                "dietary_restrictions": ["vegan"],
                "allergies": ["peanuts"],
                "disliked_ingredients": ["cilantro"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["display_name"] == "Test User"
        assert data["dietary_restrictions"] == ["vegan"]
        assert data["allergies"] == ["peanuts"]
        assert data["disliked_ingredients"] == ["cilantro"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_profile_empty_preferences(self, client):
        response = await client.post("/api/profiles", json={})
        assert response.status_code == 201
        data = response.json()
        assert data["dietary_restrictions"] == []
        assert data["allergies"] == []
        assert data["disliked_ingredients"] == []

    @pytest.mark.asyncio
    async def test_create_profile_with_display_name_only(self, client):
        response = await client.post(
            "/api/profiles",
            json={"display_name": "Chef"},
        )
        assert response.status_code == 201
        assert response.json()["display_name"] == "Chef"


class TestGetProfile:
    @pytest.fixture
    async def profile_in_db(self, async_db_session):
        profile = UserProfile(
            display_name="Test User",
            dietary_restrictions=["gluten-free"],
            allergies=["shellfish"],
            disliked_ingredients=[],
            pantry_items=["olive oil", "salt"],
        )
        async_db_session.add(profile)
        await async_db_session.commit()
        await async_db_session.refresh(profile)
        return profile.id

    @pytest.mark.asyncio
    async def test_get_profile(self, client, profile_in_db):
        response = await client.get(f"/api/profiles/{profile_in_db}")
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Test User"
        assert data["dietary_restrictions"] == ["gluten-free"]
        assert data["allergies"] == ["shellfish"]
        assert data["pantry_items"] == ["olive oil", "salt"]

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self, client):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/profiles/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "PROFILE_NOT_FOUND"


class TestUpdateProfile:
    @pytest.fixture
    async def profile_in_db(self, async_db_session):
        profile = UserProfile(
            display_name="Original",
            dietary_restrictions=["vegan"],
            allergies=[],
            disliked_ingredients=[],
        )
        async_db_session.add(profile)
        await async_db_session.commit()
        await async_db_session.refresh(profile)
        return profile.id

    @pytest.mark.asyncio
    async def test_update_profile(self, client, profile_in_db):
        response = await client.patch(
            f"/api/profiles/{profile_in_db}",
            json={
                "dietary_restrictions": ["vegan", "gluten-free"],
                "allergies": ["peanuts"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dietary_restrictions"] == ["vegan", "gluten-free"]
        assert data["allergies"] == ["peanuts"]
        assert data["display_name"] == "Original"  # unchanged

    @pytest.mark.asyncio
    async def test_update_profile_partial(self, client, profile_in_db):
        response = await client.patch(
            f"/api/profiles/{profile_in_db}",
            json={"display_name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated"
        assert data["dietary_restrictions"] == ["vegan"]  # unchanged

    @pytest.mark.asyncio
    async def test_update_profile_not_found(self, client):
        fake_id = uuid.uuid4()
        response = await client.patch(
            f"/api/profiles/{fake_id}",
            json={"display_name": "X"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_pantry_items(self, client, profile_in_db):
        response = await client.patch(
            f"/api/profiles/{profile_in_db}",
            json={"pantry_items": ["flour", "sugar", "eggs"]},
        )
        assert response.status_code == 200
        assert response.json()["pantry_items"] == ["flour", "sugar", "eggs"]


TIKTOK_URL = "https://www.tiktok.com/@user/video/123"


class TestPantryCheck:
    @pytest.fixture
    async def profile_with_pantry(self, async_db_session):
        profile = UserProfile(
            display_name="Pantry User",
            dietary_restrictions=[],
            allergies=[],
            disliked_ingredients=[],
            pantry_items=["butter", "flour"],
        )
        async_db_session.add(profile)
        await async_db_session.commit()
        await async_db_session.refresh(profile)
        return profile.id

    @pytest.fixture
    async def recipe_with_ingredients(self, async_db_session):
        job = ProcessingJob(
            source_url=TIKTOK_URL,
            normalized_url=TIKTOK_URL,
            platform="tiktok",
            status="complete",
        )
        async_db_session.add(job)
        await async_db_session.flush()

        recipe = Recipe(
            job_id=job.id,
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
            recipe_id=recipe.id, name="butter", quantity="1", unit="cup",
            order_index=0, confidence="high",
        )
        flour = Ingredient(
            recipe_id=recipe.id, name="flour", quantity="2", unit="cups",
            order_index=1, confidence="high",
        )
        eggs = Ingredient(
            recipe_id=recipe.id, name="eggs", quantity="2", unit=None,
            order_index=2, confidence="high",
        )
        async_db_session.add_all([butter, flour, eggs])
        await async_db_session.flush()

        step = Step(
            recipe_id=recipe.id, step_number=1,
            instruction="Cream butter, add flour and eggs, bake.",
            confidence="high",
        )
        async_db_session.add(step)
        await async_db_session.commit()

        return {
            "recipe_id": recipe.id,
            "ingredient_ids": {
                "butter": butter.id,
                "flour": flour.id,
                "eggs": eggs.id,
            },
        }

    @pytest.mark.asyncio
    async def test_pantry_check_success(
        self, client, profile_with_pantry, recipe_with_ingredients
    ):
        pid = profile_with_pantry
        rid = recipe_with_ingredients["recipe_id"]
        response = await client.post(f"/api/profiles/{pid}/pantry-check/{rid}")
        assert response.status_code == 200
        data = response.json()
        assert data["have_count"] == 2
        assert data["missing_count"] == 1

        by_name = {i["name"]: i for i in data["ingredients"]}
        assert by_name["butter"]["in_pantry"] is True
        assert by_name["flour"]["in_pantry"] is True
        assert by_name["eggs"]["in_pantry"] is False

    @pytest.mark.asyncio
    async def test_pantry_check_profile_not_found(
        self, client, recipe_with_ingredients
    ):
        rid = recipe_with_ingredients["recipe_id"]
        fake_pid = uuid.uuid4()
        response = await client.post(f"/api/profiles/{fake_pid}/pantry-check/{rid}")
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "PROFILE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_pantry_check_recipe_not_found(
        self, client, profile_with_pantry
    ):
        pid = profile_with_pantry
        fake_rid = uuid.uuid4()
        response = await client.post(f"/api/profiles/{pid}/pantry-check/{fake_rid}")
        assert response.status_code == 404
        assert response.json()["detail"]["error"]["code"] == "RECIPE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_pantry_check_all_in_pantry(
        self, client, async_db_session, recipe_with_ingredients
    ):
        profile = UserProfile(
            pantry_items=["butter", "flour", "eggs"],
        )
        async_db_session.add(profile)
        await async_db_session.commit()
        await async_db_session.refresh(profile)

        rid = recipe_with_ingredients["recipe_id"]
        response = await client.post(
            f"/api/profiles/{profile.id}/pantry-check/{rid}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["have_count"] == 3
        assert data["missing_count"] == 0
        assert all(i["in_pantry"] for i in data["ingredients"])

    @pytest.mark.asyncio
    async def test_pantry_check_no_pantry_items(
        self, client, async_db_session, recipe_with_ingredients
    ):
        profile = UserProfile(pantry_items=[])
        async_db_session.add(profile)
        await async_db_session.commit()
        await async_db_session.refresh(profile)

        rid = recipe_with_ingredients["recipe_id"]
        response = await client.post(
            f"/api/profiles/{profile.id}/pantry-check/{rid}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["have_count"] == 0
        assert data["missing_count"] == 3
        assert all(not i["in_pantry"] for i in data["ingredients"])

    @pytest.mark.asyncio
    async def test_pantry_check_subs_only_for_missing(
        self, client, profile_with_pantry, recipe_with_ingredients, async_db_session
    ):
        ids = recipe_with_ingredients["ingredient_ids"]
        rid = recipe_with_ingredients["recipe_id"]

        # Add substitutions to both butter (in pantry) and eggs (missing)
        sub_butter = IngredientSubstitution(
            ingredient_id=ids["butter"], recipe_id=rid,
            substitute_name="coconut oil", confidence="high", source="knowledge_base",
        )
        sub_eggs = IngredientSubstitution(
            ingredient_id=ids["eggs"], recipe_id=rid,
            substitute_name="flax eggs", confidence="medium", source="llm",
        )
        async_db_session.add_all([sub_butter, sub_eggs])
        await async_db_session.commit()

        pid = profile_with_pantry
        response = await client.post(f"/api/profiles/{pid}/pantry-check/{rid}")
        assert response.status_code == 200
        data = response.json()

        by_name = {i["name"]: i for i in data["ingredients"]}
        # Butter is in pantry — substitutions should be empty
        assert by_name["butter"]["in_pantry"] is True
        assert len(by_name["butter"]["substitutions"]) == 0
        # Eggs is missing — substitutions should be present
        assert by_name["eggs"]["in_pantry"] is False
        assert len(by_name["eggs"]["substitutions"]) == 1
        assert by_name["eggs"]["substitutions"][0]["substitute_name"] == "flax eggs"

    @pytest.mark.asyncio
    async def test_pantry_check_case_insensitive(
        self, client, async_db_session, recipe_with_ingredients
    ):
        profile = UserProfile(pantry_items=["BUTTER", "FLOUR"])
        async_db_session.add(profile)
        await async_db_session.commit()
        await async_db_session.refresh(profile)

        rid = recipe_with_ingredients["recipe_id"]
        response = await client.post(
            f"/api/profiles/{profile.id}/pantry-check/{rid}"
        )
        assert response.status_code == 200
        data = response.json()

        by_name = {i["name"]: i for i in data["ingredients"]}
        assert by_name["butter"]["in_pantry"] is True
        assert by_name["flour"]["in_pantry"] is True
