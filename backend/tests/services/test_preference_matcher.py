from app.services.preference_matcher import check_ingredient_conflicts


class TestCheckIngredientConflicts:
    def test_dairy_conflict_detected(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["butter", "flour", "sugar"],
            dietary_restrictions=["dairy-free"],
            allergies=[],
            disliked_ingredients=[],
        )
        assert "butter" in conflicts
        assert any("dairy-free" in r for r in conflicts["butter"])
        assert "flour" not in conflicts
        assert "sugar" not in conflicts

    def test_gluten_conflict_detected(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["all-purpose flour", "eggs", "salt"],
            dietary_restrictions=["gluten-free"],
            allergies=[],
            disliked_ingredients=[],
        )
        assert "all-purpose flour" in conflicts
        assert any("gluten-free" in r for r in conflicts["all-purpose flour"])

    def test_vegan_flags_dairy_and_eggs(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["butter", "eggs", "olive oil"],
            dietary_restrictions=["vegan"],
            allergies=[],
            disliked_ingredients=[],
        )
        assert "butter" in conflicts
        assert "eggs" in conflicts
        assert "olive oil" not in conflicts

    def test_allergy_conflict_detected(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["peanut butter", "jelly", "bread"],
            dietary_restrictions=[],
            allergies=["peanuts"],
            disliked_ingredients=[],
        )
        assert "peanut butter" in conflicts
        assert any("peanuts" in r for r in conflicts["peanut butter"])
        assert "jelly" not in conflicts

    def test_disliked_ingredient_flagged(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["cilantro", "lime", "onion"],
            dietary_restrictions=[],
            allergies=[],
            disliked_ingredients=["cilantro"],
        )
        assert "cilantro" in conflicts
        assert any("disliked" in r for r in conflicts["cilantro"])

    def test_no_conflicts(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["olive oil", "salt", "pepper"],
            dietary_restrictions=["dairy-free"],
            allergies=[],
            disliked_ingredients=[],
        )
        assert conflicts == {}

    def test_multiple_conflicts_per_ingredient(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["butter"],
            dietary_restrictions=["dairy-free", "vegan"],
            allergies=["dairy"],
            disliked_ingredients=[],
        )
        assert "butter" in conflicts
        assert len(conflicts["butter"]) >= 2

    def test_empty_preferences(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["butter", "flour"],
            dietary_restrictions=[],
            allergies=[],
            disliked_ingredients=[],
        )
        assert conflicts == {}

    def test_shellfish_allergy(self):
        conflicts = check_ingredient_conflicts(
            ingredient_names=["shrimp", "garlic", "pasta"],
            dietary_restrictions=[],
            allergies=["shellfish"],
            disliked_ingredients=[],
        )
        assert "shrimp" in conflicts
        assert "garlic" not in conflicts
