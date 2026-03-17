import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

_VISION_SYSTEM_PROMPT = """\
You are analyzing frames extracted from a short-form cooking video. \
Examine each frame carefully and identify cooking-related details.

Respond with ONLY valid JSON in this exact format:
{
  "ingredients_observed": ["ingredient1", "ingredient2"],
  "techniques_observed": ["technique1", "technique2"],
  "equipment_observed": ["equipment1", "equipment2"],
  "plating_notes": "description of final presentation if visible, or null",
  "frame_observations": [
    {"frame_index": 0, "description": "what is happening in this frame"}
  ]
}

Be specific about ingredients (e.g., "all-purpose flour" not just "powder"). \
List cooking techniques like "sautéing", "whisking", "folding", "kneading". \
List equipment like "stand mixer", "cast iron skillet", "baking sheet".\
"""


class VisualAnalysisError(Exception):
    def __init__(self, message: str, code: str = "VISUAL_ANALYSIS_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class VisualAnalysis:
    ingredients_observed: list[str] = field(default_factory=list)
    techniques_observed: list[str] = field(default_factory=list)
    equipment_observed: list[str] = field(default_factory=list)
    plating_notes: str | None = None
    frame_observations: list[dict] = field(default_factory=list)


def analyze_frames(frame_paths: list[str]) -> VisualAnalysis:
    """Send sampled key frames to Claude vision and return analysis."""
    if not frame_paths:
        logger.warning("No frames to analyze, returning empty analysis")
        return VisualAnalysis()

    sampled = _sample_frames(frame_paths, settings.max_vision_frames)
    logger.info("Analyzing %d frames (sampled from %d)", len(sampled), len(frame_paths))

    # Build image content blocks
    content: list[dict] = []
    for i, frame_path in enumerate(sampled):
        path = Path(frame_path)
        if not path.exists():
            logger.warning("Frame not found, skipping: %s", frame_path)
            continue

        image_data = base64.b64encode(path.read_bytes()).decode("utf-8")
        content.append(
            {
                "type": "text",
                "text": f"Frame {i + 1} of {len(sampled)}:",
            }
        )
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": image_data,
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": "Analyze all frames above and return the JSON response.",
        }
    )

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_vision_model,
            max_tokens=2048,
            system=_VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )

        response_text = response.content[0].text
        data = json.loads(response_text)

        return VisualAnalysis(
            ingredients_observed=data.get("ingredients_observed", []),
            techniques_observed=data.get("techniques_observed", []),
            equipment_observed=data.get("equipment_observed", []),
            plating_notes=data.get("plating_notes"),
            frame_observations=data.get("frame_observations", []),
        )

    except json.JSONDecodeError as e:
        raise VisualAnalysisError(
            f"Failed to parse Claude vision response as JSON: {e}",
            code="VISION_PARSE_ERROR",
        ) from e
    except anthropic.APITimeoutError as e:
        raise VisualAnalysisError(
            f"Claude vision API timed out: {e}",
            code="VISION_TIMEOUT",
        ) from e
    except anthropic.APIError as e:
        raise VisualAnalysisError(
            f"Claude vision API error: {e}",
            code="VISION_API_ERROR",
        ) from e


def _sample_frames(frame_paths: list[str], max_frames: int) -> list[str]:
    """Select evenly spaced frames, always including first and last."""
    if len(frame_paths) <= max_frames:
        return frame_paths

    indices = set()
    indices.add(0)
    indices.add(len(frame_paths) - 1)

    # Fill remaining slots evenly
    remaining = max_frames - 2
    if remaining > 0:
        step = (len(frame_paths) - 1) / (remaining + 1)
        for i in range(1, remaining + 1):
            indices.add(round(i * step))

    return [frame_paths[i] for i in sorted(indices)]
