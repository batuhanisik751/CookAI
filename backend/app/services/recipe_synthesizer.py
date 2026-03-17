import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.core.config import settings
from app.schemas.recipe import LLMRecipeOutput
from app.services.visual_analyzer import VisualAnalysis

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a culinary AI assistant that extracts structured recipes from cooking \
video transcripts and visual analysis. Your task is to produce a complete, \
accurate recipe in JSON format.

You MUST respond with ONLY valid JSON matching this exact schema:
{
  "title": "Recipe Title",
  "servings": 4,
  "prep_time_minutes": 15,
  "cook_time_minutes": 30,
  "difficulty": "easy|medium|hard",
  "cuisine_tags": ["Italian", "Pasta"],
  "ingredients": [
    {
      "name": "all-purpose flour",
      "quantity": "2",
      "unit": "cups",
      "order_index": 0,
      "notes": "sifted",
      "confidence": "high|medium|low"
    }
  ],
  "steps": [
    {
      "step_number": 1,
      "instruction": "Clear, actionable instruction",
      "duration_estimate": "5 minutes",
      "tip": "Optional helpful tip",
      "confidence": "high|medium|low"
    }
  ],
  "confidence": {
    "title": "high|medium|low",
    "servings": "high|medium|low",
    "prep_time": "high|medium|low",
    "cook_time": "high|medium|low",
    "ingredients": "high|medium|low",
    "steps": "high|medium|low",
    "overall": "high|medium|low"
  },
  "review_flags": ["list of issues or uncertainties, if any"]
}

Guidelines:
- Standardize units (cups, tablespoons, teaspoons, grams, ounces, etc.)
- Number steps sequentially starting from 1
- Set confidence to "low" for any quantities or steps you are uncertain about
- Add review_flags for anything ambiguous (unclear quantities, missing steps, etc.)
- If servings are not mentioned, estimate based on ingredient quantities
- Infer difficulty from technique complexity and number of steps
- Use the video caption and creator info for context clues about the recipe\
"""


class RecipeSynthesisError(Exception):
    def __init__(self, message: str, code: str = "SYNTHESIS_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class SynthesisResult:
    recipe_data: LLMRecipeOutput
    needs_review: bool
    review_flags: list[str] = field(default_factory=list)


def synthesize_recipe(
    transcript: str,
    visual_analysis: VisualAnalysis,
    metadata: dict,
) -> SynthesisResult:
    """Combine transcript + visual analysis + metadata and synthesize a recipe."""
    prompt = _build_synthesis_prompt(transcript, visual_analysis, metadata)

    logger.info("Synthesizing recipe from transcript and visual analysis")

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.max_recipe_tokens,
            system=_SYNTHESIS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text
        data = json.loads(response_text)
        recipe = LLMRecipeOutput(**data)

    except json.JSONDecodeError as e:
        raise RecipeSynthesisError(
            f"Failed to parse recipe JSON from Claude: {e}",
            code="SYNTHESIS_PARSE_ERROR",
        ) from e
    except anthropic.APITimeoutError as e:
        raise RecipeSynthesisError(
            f"Claude API timed out during synthesis: {e}",
            code="SYNTHESIS_TIMEOUT",
        ) from e
    except anthropic.APIError as e:
        raise RecipeSynthesisError(
            f"Claude API error during synthesis: {e}",
            code="SYNTHESIS_API_ERROR",
        ) from e
    except Exception as e:
        raise RecipeSynthesisError(
            f"Recipe synthesis failed: {e}",
            code="SYNTHESIS_FAILED",
        ) from e

    # Post-generation validation
    validation_flags = _validate_recipe(recipe)
    all_flags = recipe.review_flags + validation_flags

    # Determine if review is needed
    needs_review = bool(all_flags) or _has_low_confidence(recipe)

    logger.info(
        "Recipe synthesized: title=%s, needs_review=%s, flags=%d",
        recipe.title,
        needs_review,
        len(all_flags),
    )

    return SynthesisResult(
        recipe_data=recipe,
        needs_review=needs_review,
        review_flags=all_flags,
    )


def _build_synthesis_prompt(
    transcript: str,
    visual_analysis: VisualAnalysis,
    metadata: dict,
) -> str:
    """Build the user prompt with all available context."""
    sections = []

    # Video metadata
    caption = metadata.get("caption", "")
    creator = metadata.get("creator_handle", "")
    if caption or creator:
        meta_parts = []
        if creator:
            meta_parts.append(f"Creator: {creator}")
        if caption:
            meta_parts.append(f"Caption: {caption}")
        sections.append("## Video Info\n" + "\n".join(meta_parts))

    # Transcript
    sections.append(f"## Transcript\n{transcript}")

    # Visual analysis
    if visual_analysis.ingredients_observed:
        sections.append(
            "## Ingredients Seen in Video\n"
            + ", ".join(visual_analysis.ingredients_observed)
        )
    if visual_analysis.techniques_observed:
        sections.append(
            "## Cooking Techniques Observed\n"
            + ", ".join(visual_analysis.techniques_observed)
        )
    if visual_analysis.equipment_observed:
        sections.append(
            "## Equipment Used\n" + ", ".join(visual_analysis.equipment_observed)
        )
    if visual_analysis.plating_notes:
        sections.append(f"## Plating/Presentation\n{visual_analysis.plating_notes}")
    if visual_analysis.frame_observations:
        obs_lines = [
            f"- Frame {o.get('frame_index', '?')}: {o.get('description', '')}"
            for o in visual_analysis.frame_observations
        ]
        sections.append("## Frame-by-Frame Observations\n" + "\n".join(obs_lines))

    sections.append(
        "## Task\n"
        "Extract a complete structured recipe from the information above. "
        "Return ONLY the JSON response."
    )

    return "\n\n".join(sections)


def _validate_recipe(recipe: LLMRecipeOutput) -> list[str]:
    """Post-generation validation checks."""
    flags = []

    # Check that ingredients appear in at least one step
    step_text = " ".join(s.instruction.lower() for s in recipe.steps)
    missing = []
    for ing in recipe.ingredients:
        # Check if the ingredient name (or a reasonable substring) appears in steps
        name_lower = ing.name.lower()
        # Try full name first, then first word (e.g., "all-purpose flour" -> "flour")
        words = name_lower.split()
        found = name_lower in step_text or any(
            w in step_text for w in words if len(w) > 2
        )
        if not found:
            missing.append(ing.name)

    if missing:
        flags.append(f"Ingredients not mentioned in steps: {', '.join(missing)}")

    # Check sequential step numbers
    expected = list(range(1, len(recipe.steps) + 1))
    actual = [s.step_number for s in recipe.steps]
    if actual != expected:
        flags.append("Steps are not numbered sequentially")

    # Check quantity coverage
    total = len(recipe.ingredients)
    missing_qty = sum(1 for i in recipe.ingredients if not i.quantity)
    if total > 0 and missing_qty / total > 0.3:
        flags.append(f"{missing_qty}/{total} ingredients missing quantities")

    return flags


def _has_low_confidence(recipe: LLMRecipeOutput) -> bool:
    """Check if any confidence score is 'low'."""
    confidence = recipe.confidence
    fields = [
        confidence.title,
        confidence.servings,
        confidence.prep_time,
        confidence.cook_time,
        confidence.ingredients,
        confidence.steps,
        confidence.overall,
    ]
    return any(f == "low" for f in fields)
