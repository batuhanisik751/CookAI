import logging
import re
from dataclasses import dataclass
from pathlib import Path

import openai

from app.core.config import settings

logger = logging.getLogger(__name__)

# Filler words to remove (word-boundary matched, case-insensitive)
_FILLER_PATTERN = re.compile(
    r"\b(um|uh|uhh|umm|like|you know|basically|literally|actually|so yeah"
    r"|I mean|right|okay so)\b",
    re.IGNORECASE,
)

# Measurement normalizations: spoken form -> standardized form
_MEASUREMENT_MAP = [
    (re.compile(r"\bhalf a cup\b", re.IGNORECASE), "1/2 cup"),
    (re.compile(r"\bhalf a teaspoon\b", re.IGNORECASE), "1/2 teaspoon"),
    (re.compile(r"\bhalf a tablespoon\b", re.IGNORECASE), "1/2 tablespoon"),
    (re.compile(r"\ba quarter cup\b", re.IGNORECASE), "1/4 cup"),
    (re.compile(r"\bthree quarters? cup\b", re.IGNORECASE), "3/4 cup"),
    (re.compile(r"\ba cup\b", re.IGNORECASE), "1 cup"),
    (re.compile(r"\ba teaspoon\b", re.IGNORECASE), "1 teaspoon"),
    (re.compile(r"\ba tablespoon\b", re.IGNORECASE), "1 tablespoon"),
    (re.compile(r"\ban egg\b", re.IGNORECASE), "1 egg"),
    (re.compile(r"\ba pinch\b", re.IGNORECASE), "1 pinch"),
]

# Collapse multiple spaces into one
_MULTI_SPACE = re.compile(r" {2,}")


class TranscriptionError(Exception):
    def __init__(self, message: str, code: str = "TRANSCRIPTION_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class TranscriptionResult:
    raw_transcript: str
    cleaned_transcript: str
    language: str
    duration_seconds: float


def transcribe_audio(audio_path: str) -> TranscriptionResult:
    """Send audio file to OpenAI Whisper API and return transcription."""
    path = Path(audio_path)
    if not path.exists():
        raise TranscriptionError(
            f"Audio file not found: {audio_path}",
            code="FILE_NOT_FOUND",
        )

    logger.info("Transcribing audio: %s", audio_path)

    try:
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.transcription_timeout_seconds,
        )

        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                model=settings.whisper_model,
                file=audio_file,
                response_format="verbose_json",
            )

        raw_text = response.text
        language = getattr(response, "language", "en") or "en"
        duration = getattr(response, "duration", 0.0) or 0.0

        cleaned_text = _clean_transcript(raw_text)

        logger.info(
            "Transcription complete: language=%s, duration=%.1fs, length=%d chars",
            language,
            duration,
            len(raw_text),
        )

        return TranscriptionResult(
            raw_transcript=raw_text,
            cleaned_transcript=cleaned_text,
            language=language,
            duration_seconds=duration,
        )

    except openai.APITimeoutError as e:
        raise TranscriptionError(
            f"Whisper API timed out: {e}",
            code="TRANSCRIPTION_TIMEOUT",
        ) from e
    except openai.APIError as e:
        raise TranscriptionError(
            f"Whisper API error: {e}",
            code="TRANSCRIPTION_API_ERROR",
        ) from e


def _clean_transcript(text: str) -> str:
    """Remove filler words and normalize measurements in transcript."""
    # Remove filler words
    cleaned = _FILLER_PATTERN.sub("", text)

    # Normalize measurements
    for pattern, replacement in _MEASUREMENT_MAP:
        cleaned = pattern.sub(replacement, cleaned)

    # Collapse multiple spaces
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()

    return cleaned
