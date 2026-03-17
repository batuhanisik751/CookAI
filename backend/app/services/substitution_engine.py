"""Context-aware ingredient substitution engine powered by Claude API."""

import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.core.config import settings
from app.schemas.recipe import IngredientSchema, StepSchema
from app.schemas.substitution import LLMSubstitutionItem, LLMSubstitutionOutput

logger = logging.getLogger(__name__)

_SUBSTITUTION_SYSTEM_PROMPT = """\
You are a culinary AI assistant specializing in ingredient substitutions. \
Given a recipe with its ingredients and steps, analyze each ingredient's role \
and suggest 2-3 substitutions.

You MUST respond with ONLY valid JSON matching this exact schema:
{
  "substitutions": [
    {
      "original_ingredient": "butter",
      "role_in_recipe": "structural|flavor|moisture|leavening|binding|fat",
      "substitutions": [
        {
          "substitute_name": "coconut oil",
          "substitute_quantity": "1",
          "substitute_unit": "cup",
          "ratio_explanation": "Use equal amount of coconut oil",
          "dietary_tags": ["vegan", "dairy-free"],
          "impact_notes": "Adds slight coconut flavor, works well in baking",
          "confidence": "high|medium|low"
        }
      ]
    }
  ]
}

Guidelines:
- Analyze each ingredient's role in the specific recipe context
- Consider how the substitution affects cooking technique, timing, and texture
- Provide specific ratio adjustments (not just "use less" but exact amounts)
- Tag each substitution with relevant dietary categories: vegan, dairy-free, \
gluten-free, nut-free, egg-free
- Include trade-off notes explaining flavor/texture differences
- For structural ingredients (flour, eggs), explain technique adjustments needed
- Suggest 2-3 substitutions per ingredient, prioritizing common pantry items
- Set confidence to "low" for substitutions that significantly alter the recipe\
"""


class SubstitutionError(Exception):
    def __init__(self, message: str, code: str = "SUBSTITUTION_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class SubstitutionResult:
    substitutions: list[LLMSubstitutionItem]
    raw_response: str = ""
    token_usage: dict = field(default_factory=dict)


def generate_substitutions(
    recipe_title: str,
    ingredients: list[IngredientSchema],
    steps: list[StepSchema],
    dietary_filters: list[str] | None = None,
) -> SubstitutionResult:
    """Generate context-aware substitutions for all ingredients in a recipe."""
    prompt = _build_substitution_prompt(
        recipe_title, ingredients, steps, dietary_filters
    )

    logger.info(
        "Generating substitutions for recipe=%s, ingredients=%d",
        recipe_title,
        len(ingredients),
    )

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.max_substitution_tokens,
            system=_SUBSTITUTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text
        data = json.loads(response_text)
        output = LLMSubstitutionOutput(**data)

    except json.JSONDecodeError as e:
        raise SubstitutionError(
            f"Failed to parse substitution JSON from Claude: {e}",
            code="SUBSTITUTION_PARSE_ERROR",
        ) from e
    except anthropic.APITimeoutError as e:
        raise SubstitutionError(
            f"Claude API timed out during substitution generation: {e}",
            code="SUBSTITUTION_TIMEOUT",
        ) from e
    except anthropic.APIError as e:
        raise SubstitutionError(
            f"Claude API error during substitution generation: {e}",
            code="SUBSTITUTION_API_ERROR",
        ) from e
    except Exception as e:
        raise SubstitutionError(
            f"Substitution generation failed: {e}",
            code="SUBSTITUTION_FAILED",
        ) from e

    logger.info(
        "Substitutions generated for recipe=%s, items=%d",
        recipe_title,
        len(output.substitutions),
    )

    return SubstitutionResult(
        substitutions=output.substitutions,
        raw_response=response_text,
        token_usage={
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
    )


def _build_substitution_prompt(
    recipe_title: str,
    ingredients: list[IngredientSchema],
    steps: list[StepSchema],
    dietary_filters: list[str] | None = None,
) -> str:
    """Build the user prompt with recipe context for substitution generation."""
    sections = []

    sections.append(f"## Recipe: {recipe_title}")

    # Ingredients list
    ing_lines = []
    for ing in ingredients:
        parts = []
        if ing.quantity:
            parts.append(ing.quantity)
        if ing.unit:
            parts.append(ing.unit)
        parts.append(ing.name)
        if ing.notes:
            parts.append(f"({ing.notes})")
        ing_lines.append(f"- {' '.join(parts)}")
    sections.append("## Ingredients\n" + "\n".join(ing_lines))

    # Steps
    step_lines = [f"{s.step_number}. {s.instruction}" for s in steps]
    sections.append("## Steps\n" + "\n".join(step_lines))

    # Dietary filters
    if dietary_filters:
        sections.append(
            "## Dietary Requirements\n"
            f"Prioritize substitutions for: {', '.join(dietary_filters)}.\n"
            "Ensure all suggestions for restricted ingredients comply with these"
            " requirements."
        )

    sections.append(
        "## Task\n"
        "Analyze each ingredient's role in this recipe and provide 2-3 substitution "
        "options per ingredient. Consider the cooking techniques used in the steps. "
        "Return ONLY the JSON response."
    )

    return "\n\n".join(sections)
