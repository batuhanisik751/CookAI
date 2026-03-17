import json
import logging
from dataclasses import dataclass, field

import anthropic

from app.core.config import settings
from app.schemas.recipe import LLMRecipeOutput

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are a culinary AI assistant that extracts structured recipes from cooking \
video transcripts and metadata. Your task is to produce a complete, \
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
    metadata: dict,
    caption_source: str = "auto",
) -> SynthesisResult:
    """Combine transcript + metadata and synthesize a recipe via Claude."""
    prompt = _build_synthesis_prompt(transcript, metadata, caption_source)

    logger.info("Synthesizing recipe from transcript (source=%s)", caption_source)

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

    # Auto-flag description-only recipes
    if caption_source == "description_only":
        all_flags.append("Recipe extracted from video description only (no transcript)")

    # Determine if review is needed
    needs_review = (
        bool(all_flags)
        or _has_low_confidence(recipe)
        or caption_source == "description_only"
    )

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
    metadata: dict,
    caption_source: str,
) -> str:
    """Build the user prompt with all available context."""
    sections = []

    # Video metadata
    caption = metadata.get("caption", "")
    creator = metadata.get("creator_handle", "")
    description = metadata.get("description", "")
    hashtags = metadata.get("hashtags", [])

    if caption or creator or description or hashtags:
        meta_parts = []
        if creator:
            meta_parts.append(f"Creator: {creator}")
        if caption:
            meta_parts.append(f"Caption: {caption}")
        if description and description != caption:
            meta_parts.append(f"Description: {description}")
        if hashtags:
            meta_parts.append(f"Hashtags: {', '.join(hashtags[:20])}")
        sections.append("## Video Info\n" + "\n".join(meta_parts))

    # Caption source quality note
    if caption_source == "auto":
        sections.append(
            "## Note\n"
            "The transcript below comes from auto-generated captions and may "
            "contain errors, especially for cooking terms and measurements."
        )
    elif caption_source == "description_only":
        sections.append(
            "## Note\n"
            "No spoken transcript was available for this video. The text below "
            "is from the video description only. Extract what recipe information "
            "you can, but be conservative with confidence scores."
        )

    # Transcript
    sections.append(f"## Transcript\n{transcript}")

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
