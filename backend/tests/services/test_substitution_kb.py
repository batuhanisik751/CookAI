import pytest

from app.models.substitution import SubstitutionKnowledgeBase
from app.services.substitution_kb import lookup_bulk_substitutions, lookup_substitutions


class TestLookupSubstitutions:
    @pytest.fixture
    async def seeded_kb(self, async_db_session):
        """Seed the KB with a few entries for testing."""
        entries = [
            SubstitutionKnowledgeBase(
                original_ingredient="butter",
                substitute_ingredient="coconut oil",
                ratio="1:1",
                category="dairy-free",
                flavor_similarity="medium",
                notes="Works in baking",
                is_common_pantry=True,
            ),
            SubstitutionKnowledgeBase(
                original_ingredient="butter",
                substitute_ingredient="olive oil",
                ratio="3/4 cup per 1 cup",
                category="dairy-free",
                flavor_similarity="low",
                notes="Best for savory",
                is_common_pantry=True,
            ),
            SubstitutionKnowledgeBase(
                original_ingredient="butter",
                substitute_ingredient="vegan butter",
                ratio="1:1",
                category="vegan",
                flavor_similarity="high",
                notes="Direct swap",
                is_common_pantry=False,
            ),
            SubstitutionKnowledgeBase(
                original_ingredient="milk",
                substitute_ingredient="oat milk",
                ratio="1:1",
                category="dairy-free",
                flavor_similarity="high",
                notes="Creamy texture",
                is_common_pantry=True,
            ),
        ]
        for entry in entries:
            async_db_session.add(entry)
        await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_lookup_single_ingredient(self, async_db_session, seeded_kb):
        results = await lookup_substitutions(async_db_session, "butter")
        assert len(results) == 3
        names = {r.substitute_ingredient for r in results}
        assert "coconut oil" in names
        assert "olive oil" in names
        assert "vegan butter" in names

    @pytest.mark.asyncio
    async def test_lookup_with_category_filter(self, async_db_session, seeded_kb):
        results = await lookup_substitutions(
            async_db_session, "butter", category="dairy-free"
        )
        assert len(results) == 2
        assert all(r.category == "dairy-free" for r in results)

    @pytest.mark.asyncio
    async def test_lookup_nonexistent_ingredient(self, async_db_session, seeded_kb):
        results = await lookup_substitutions(async_db_session, "xyznonexistent")
        assert results == []

    @pytest.mark.asyncio
    async def test_case_insensitive_lookup(self, async_db_session, seeded_kb):
        results = await lookup_substitutions(async_db_session, "Butter")
        assert len(results) == 3


class TestBulkLookup:
    @pytest.fixture
    async def seeded_kb(self, async_db_session):
        entries = [
            SubstitutionKnowledgeBase(
                original_ingredient="butter",
                substitute_ingredient="coconut oil",
                ratio="1:1",
                category="dairy-free",
            ),
            SubstitutionKnowledgeBase(
                original_ingredient="milk",
                substitute_ingredient="oat milk",
                ratio="1:1",
                category="dairy-free",
            ),
        ]
        for entry in entries:
            async_db_session.add(entry)
        await async_db_session.commit()

    @pytest.mark.asyncio
    async def test_bulk_lookup(self, async_db_session, seeded_kb):
        results = await lookup_bulk_substitutions(
            async_db_session, ["butter", "milk", "salt"]
        )
        assert "butter" in results
        assert "milk" in results
        assert "salt" not in results

    @pytest.mark.asyncio
    async def test_bulk_lookup_with_category_filter(self, async_db_session, seeded_kb):
        results = await lookup_bulk_substitutions(
            async_db_session, ["butter"], categories=["dairy-free"]
        )
        assert "butter" in results
        assert all(e.category == "dairy-free" for e in results["butter"])
