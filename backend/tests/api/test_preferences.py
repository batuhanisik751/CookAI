import uuid

import pytest

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
