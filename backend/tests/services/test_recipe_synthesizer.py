import json
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from app.schemas.recipe import (
    ConfidenceScores,
    IngredientSchema,
    LLMRecipeOutput,
    StepSchema,
)
from app.services.recipe_synthesizer import (
    RecipeSynthesisError,
    SynthesisResult,
    _has_low_confidence,
    _validate_recipe,
    synthesize_recipe,
)
from app.services.visual_analyzer import VisualAnalysis


@pytest.fixture
def sample_llm_output():
    return {
        "title": "Classic Pancakes",
        "servings": 4,
        "prep_time_minutes": 10,
        "cook_time_minutes": 15,
        "difficulty": "easy",
        "cuisine_tags": ["American", "Breakfast"],
        "ingredients": [
            {
                "name": "flour",
                "quantity": "2",
                "unit": "cups",
                "order_index": 0,
                "confidence": "high",
            },
            {
                "name": "eggs",
                "quantity": "2",
                "unit": None,
                "order_index": 1,
                "confidence": "high",
            },
            {
                "name": "milk",
                "quantity": "1",
                "unit": "cup",
                "order_index": 2,
                "confidence": "high",
            },
            {
                "name": "butter",
                "quantity": "2",
                "unit": "tablespoons",
                "order_index": 3,
                "confidence": "high",
            },
        ],
        "steps": [
            {
                "step_number": 1,
                "instruction": "Mix the flour, eggs, and milk in a bowl.",
                "confidence": "high",
            },
            {
                "step_number": 2,
                "instruction": "Melt the butter and add to the batter.",
                "confidence": "high",
            },
            {
                "step_number": 3,
                "instruction": "Cook on a griddle until golden brown.",
                "confidence": "high",
            },
        ],
        "confidence": {
            "title": "high",
            "servings": "medium",
            "prep_time": "medium",
            "cook_time": "medium",
            "ingredients": "high",
            "steps": "high",
            "overall": "high",
        },
        "review_flags": [],
    }


@pytest.fixture
def sample_visual_analysis():
    return VisualAnalysis(
        ingredients_observed=["flour", "eggs", "milk", "butter"],
        techniques_observed=["mixing", "pan-frying"],
        equipment_observed=["mixing bowl", "griddle", "spatula"],
        plating_notes="Stacked pancakes with maple syrup",
        frame_observations=[
            {"frame_index": 0, "description": "Ingredients on counter"},
        ],
    )


@pytest.fixture
def sample_metadata():
    return {
        "caption": "Easy pancake recipe! #breakfast #cooking",
        "creator_handle": "chef_demo",
        "duration_seconds": 45.0,
    }


@pytest.fixture
def mock_claude_synthesis(sample_llm_output):
    with patch("app.services.recipe_synthesizer.anthropic.Anthropic") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        response = MagicMock()
        response.content = [MagicMock(text=json.dumps(sample_llm_output))]
        client.messages.create.return_value = response
        yield client


class TestSynthesizeRecipe:
    def test_success(
        self,
        mock_claude_synthesis,
        sample_visual_analysis,
        sample_metadata,
    ):
        result = synthesize_recipe(
            transcript="Mix flour eggs and milk, melt butter, cook on griddle",
            visual_analysis=sample_visual_analysis,
            metadata=sample_metadata,
        )

        assert isinstance(result, SynthesisResult)
        assert result.recipe_data.title == "Classic Pancakes"
        assert len(result.recipe_data.ingredients) == 4
        assert len(result.recipe_data.steps) == 3
        assert result.recipe_data.difficulty == "easy"
        mock_claude_synthesis.messages.create.assert_called_once()

    def test_api_error(self, sample_visual_analysis, sample_metadata):
        with patch("app.services.recipe_synthesizer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = anthropic.APIError(
                message="Server error",
                request=MagicMock(),
                body=None,
            )

            with pytest.raises(RecipeSynthesisError) as exc_info:
                synthesize_recipe("transcript", sample_visual_analysis, sample_metadata)
            assert exc_info.value.code == "SYNTHESIS_API_ERROR"

    def test_timeout(self, sample_visual_analysis, sample_metadata):
        with patch("app.services.recipe_synthesizer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            client.messages.create.side_effect = anthropic.APITimeoutError(
                request=MagicMock()
            )

            with pytest.raises(RecipeSynthesisError) as exc_info:
                synthesize_recipe("transcript", sample_visual_analysis, sample_metadata)
            assert exc_info.value.code == "SYNTHESIS_TIMEOUT"

    def test_invalid_json_response(self, sample_visual_analysis, sample_metadata):
        with patch("app.services.recipe_synthesizer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            response = MagicMock()
            response.content = [MagicMock(text="not json at all")]
            client.messages.create.return_value = response

            with pytest.raises(RecipeSynthesisError) as exc_info:
                synthesize_recipe("transcript", sample_visual_analysis, sample_metadata)
            assert exc_info.value.code == "SYNTHESIS_PARSE_ERROR"

    def test_needs_review_when_low_confidence(
        self,
        sample_llm_output,
        sample_visual_analysis,
        sample_metadata,
    ):
        sample_llm_output["confidence"]["overall"] = "low"

        with patch("app.services.recipe_synthesizer.anthropic.Anthropic") as mock_cls:
            client = MagicMock()
            mock_cls.return_value = client
            response = MagicMock()
            response.content = [MagicMock(text=json.dumps(sample_llm_output))]
            client.messages.create.return_value = response

            result = synthesize_recipe(
                "transcript", sample_visual_analysis, sample_metadata
            )
            assert result.needs_review is True


class TestValidateRecipe:
    def test_valid_recipe(self):
        recipe = LLMRecipeOutput(
            title="Test",
            ingredients=[
                IngredientSchema(name="flour", quantity="1", unit="cup", order_index=0),
                IngredientSchema(
                    name="sugar", quantity="1/2", unit="cup", order_index=1
                ),
            ],
            steps=[
                StepSchema(
                    step_number=1, instruction="Mix the flour and sugar together."
                ),
                StepSchema(step_number=2, instruction="Bake at 350 degrees."),
            ],
            confidence=ConfidenceScores(),
        )
        flags = _validate_recipe(recipe)
        assert flags == []

    def test_missing_ingredient_in_steps(self):
        recipe = LLMRecipeOutput(
            title="Test",
            ingredients=[
                IngredientSchema(name="flour", quantity="1", unit="cup", order_index=0),
                IngredientSchema(
                    name="xanthan gum", quantity="1", unit="tsp", order_index=1
                ),
            ],
            steps=[
                StepSchema(step_number=1, instruction="Mix the flour."),
            ],
            confidence=ConfidenceScores(),
        )
        flags = _validate_recipe(recipe)
        assert any("xanthan gum" in f for f in flags)

    def test_non_sequential_steps(self):
        recipe = LLMRecipeOutput(
            title="Test",
            ingredients=[
                IngredientSchema(name="flour", quantity="1", unit="cup", order_index=0),
            ],
            steps=[
                StepSchema(step_number=1, instruction="Add flour."),
                StepSchema(step_number=3, instruction="Mix."),
            ],
            confidence=ConfidenceScores(),
        )
        flags = _validate_recipe(recipe)
        assert any("sequential" in f.lower() for f in flags)

    def test_missing_quantities_flagged(self):
        recipe = LLMRecipeOutput(
            title="Test",
            ingredients=[
                IngredientSchema(name="flour", quantity=None, unit=None, order_index=0),
                IngredientSchema(name="sugar", quantity=None, unit=None, order_index=1),
                IngredientSchema(name="salt", quantity=None, unit=None, order_index=2),
            ],
            steps=[
                StepSchema(step_number=1, instruction="Mix flour, sugar, and salt."),
            ],
            confidence=ConfidenceScores(),
        )
        flags = _validate_recipe(recipe)
        assert any("missing quantities" in f.lower() for f in flags)


class TestHasLowConfidence:
    def test_all_high(self):
        recipe = LLMRecipeOutput(
            title="Test",
            ingredients=[],
            steps=[],
            confidence=ConfidenceScores(),
        )
        assert _has_low_confidence(recipe) is False

    def test_one_low(self):
        recipe = LLMRecipeOutput(
            title="Test",
            ingredients=[],
            steps=[],
            confidence=ConfidenceScores(overall="low"),
        )
        assert _has_low_confidence(recipe) is True
