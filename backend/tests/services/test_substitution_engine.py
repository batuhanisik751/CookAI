import json
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from app.schemas.recipe import IngredientSchema, StepSchema
from app.services.substitution_engine import (
    SubstitutionError,
    SubstitutionResult,
    _build_substitution_prompt,
    generate_substitutions,
)


@pytest.fixture
def sample_ingredients():
    return [
        IngredientSchema(name="butter", quantity="1", unit="cup", order_index=0),
        IngredientSchema(name="flour", quantity="2", unit="cups", order_index=1),
        IngredientSchema(name="eggs", quantity="2", unit=None, order_index=2),
    ]


@pytest.fixture
def sample_steps():
    return [
        StepSchema(step_number=1, instruction="Cream the butter and sugar."),
        StepSchema(step_number=2, instruction="Add flour and eggs, mix well."),
        StepSchema(step_number=3, instruction="Bake at 350°F for 25 minutes."),
    ]


@pytest.fixture
def sample_substitution_llm_output():
    return {
        "substitutions": [
            {
                "original_ingredient": "butter",
                "role_in_recipe": "fat",
                "substitutions": [
                    {
                        "substitute_name": "coconut oil",
                        "substitute_quantity": "1",
                        "substitute_unit": "cup",
                        "ratio_explanation": "Use equal amount",
                        "dietary_tags": ["vegan", "dairy-free"],
                        "impact_notes": "Slight coconut flavor",
                        "confidence": "high",
                    },
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
                        "ratio_explanation": "1:1 but add extra binding",
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
                        "substitute_unit": "tbsp ground flax + 6 tbsp water",
                        "ratio_explanation": "1 tbsp flax + 3 tbsp water per egg",
                        "dietary_tags": ["vegan", "egg-free"],
                        "impact_notes": "Good binding but less rise",
                        "confidence": "medium",
                    },
                ],
            },
        ]
    }


@pytest.fixture
def mock_claude_substitution(sample_substitution_llm_output):
    with patch("app.services.substitution_engine.anthropic.Anthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps(sample_substitution_llm_output))]
        response.usage = MagicMock(input_tokens=500, output_tokens=800)
        client.messages.create.return_value = response
        yield client


class TestGenerateSubstitutions:
    def test_success(self, mock_claude_substitution, sample_ingredients, sample_steps):
        result = generate_substitutions(
            recipe_title="Butter Cookies",
            ingredients=sample_ingredients,
            steps=sample_steps,
        )
        assert isinstance(result, SubstitutionResult)
        assert len(result.substitutions) == 3
        assert result.substitutions[0].original_ingredient == "butter"
        assert len(result.substitutions[0].substitutions) == 2
        mock_claude_substitution.messages.create.assert_called_once()

    def test_token_usage_tracked(
        self, mock_claude_substitution, sample_ingredients, sample_steps
    ):
        result = generate_substitutions(
            recipe_title="Butter Cookies",
            ingredients=sample_ingredients,
            steps=sample_steps,
        )
        assert result.token_usage["input_tokens"] == 500
        assert result.token_usage["output_tokens"] == 800

    def test_api_error(self, sample_ingredients, sample_steps):
        with patch("app.services.substitution_engine.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = anthropic.APIError(
                message="Server error",
                request=MagicMock(),
                body=None,
            )

            with pytest.raises(SubstitutionError) as exc_info:
                generate_substitutions("Test", sample_ingredients, sample_steps)
            assert exc_info.value.code == "SUBSTITUTION_API_ERROR"

    def test_timeout(self, sample_ingredients, sample_steps):
        with patch("app.services.substitution_engine.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = anthropic.APITimeoutError(
                request=MagicMock()
            )

            with pytest.raises(SubstitutionError) as exc_info:
                generate_substitutions("Test", sample_ingredients, sample_steps)
            assert exc_info.value.code == "SUBSTITUTION_TIMEOUT"

    def test_invalid_json_response(self, sample_ingredients, sample_steps):
        with patch("app.services.substitution_engine.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            response = MagicMock()
            response.content = [MagicMock(text="not json")]
            client.messages.create.return_value = response

            with pytest.raises(SubstitutionError) as exc_info:
                generate_substitutions("Test", sample_ingredients, sample_steps)
            assert exc_info.value.code == "SUBSTITUTION_PARSE_ERROR"

    def test_all_ingredients_get_substitutions(
        self, mock_claude_substitution, sample_ingredients, sample_steps
    ):
        result = generate_substitutions(
            recipe_title="Butter Cookies",
            ingredients=sample_ingredients,
            steps=sample_steps,
        )
        ingredient_names = {s.original_ingredient for s in result.substitutions}
        assert "butter" in ingredient_names
        assert "flour" in ingredient_names
        assert "eggs" in ingredient_names


class TestBuildSubstitutionPrompt:
    def test_includes_recipe_title(self, sample_ingredients, sample_steps):
        prompt = _build_substitution_prompt(
            "Butter Cookies", sample_ingredients, sample_steps
        )
        assert "Butter Cookies" in prompt

    def test_includes_all_ingredients(self, sample_ingredients, sample_steps):
        prompt = _build_substitution_prompt("Test", sample_ingredients, sample_steps)
        assert "butter" in prompt
        assert "flour" in prompt
        assert "eggs" in prompt

    def test_includes_dietary_filters(self, sample_ingredients, sample_steps):
        prompt = _build_substitution_prompt(
            "Test",
            sample_ingredients,
            sample_steps,
            dietary_filters=["vegan", "gluten-free"],
        )
        assert "vegan" in prompt
        assert "gluten-free" in prompt

    def test_no_dietary_filters(self, sample_ingredients, sample_steps):
        prompt = _build_substitution_prompt("Test", sample_ingredients, sample_steps)
        assert "Dietary Requirements" not in prompt
