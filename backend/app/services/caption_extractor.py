import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

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

# VTT/SRT timestamp line pattern — matches the full line including end time
_TIMESTAMP_PATTERN = re.compile(
    r"^\d{2}:\d{2}[:\.]?\d{0,2}[\.\,]?\d{0,3}\s*-->.*$", re.MULTILINE
)

# SRT sequence number pattern (standalone line with just a number)
_SRT_SEQUENCE_PATTERN = re.compile(r"^\d+$", re.MULTILINE)

# HTML tag pattern
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# VTT header
_VTT_HEADER_PATTERN = re.compile(r"^WEBVTT.*$", re.MULTILINE)

# VTT metadata lines (NOTE, STYLE, etc.)
_VTT_META_PATTERN = re.compile(r"^(NOTE|STYLE|REGION)\b.*$", re.MULTILINE)


class CaptionExtractionError(Exception):
    """Raised when caption extraction fails."""

    def __init__(self, message: str, code: str = "CAPTION_EXTRACTION_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class CaptionResult:
    raw_transcript: str
    cleaned_transcript: str
    caption_source: str  # "manual", "auto", or "description_only"
    metadata: dict = field(default_factory=dict)
    language: str | None = None


def extract_captions(url: str, job_id: str) -> CaptionResult:
    """
    Extract captions and metadata from a video URL without downloading the video.

    Uses yt-dlp with --skip-download to fetch subtitles and metadata only.

    Args:
        url: Pre-validated video URL.
        job_id: UUID string for organizing temp subtitle files.

    Returns:
        CaptionResult with transcript, caption source, and metadata.

    Raises:
        CaptionExtractionError: On extraction failure.
    """
    output_dir = str(Path(settings.temp_media_dir) / job_id)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Step 1: Extract info and check duration
    info = _extract_info(url, output_dir)

    duration = info.get("duration")
    if duration and duration > settings.max_video_duration_seconds:
        raise CaptionExtractionError(
            f"Video duration ({duration:.0f}s) exceeds limit "
            f"({settings.max_video_duration_seconds}s).",
            code="DURATION_EXCEEDED",
        )

    metadata = _extract_metadata(info)

    # Step 2: Try to get subtitle files
    _download_subtitles(url, output_dir)

    # Step 3: Find and parse subtitles with fallback chain
    sub_path, caption_source = _find_subtitle_file(output_dir)

    if sub_path:
        raw_transcript = _parse_subtitles(sub_path)
        if not raw_transcript.strip():
            # Empty subtitle file — fall back to description
            raw_transcript = metadata.get("description") or metadata.get("caption", "")
            caption_source = "description_only"
    else:
        # No subtitle files found — use description
        raw_transcript = metadata.get("description") or metadata.get("caption", "")
        caption_source = "description_only"

    if not raw_transcript.strip():
        raise CaptionExtractionError(
            "No captions, subtitles, or description available for this video.",
            code="NO_TRANSCRIPT_AVAILABLE",
        )

    cleaned_transcript = _clean_transcript(raw_transcript)

    # Detect language from subtitle metadata
    language = _detect_language(info, caption_source)

    logger.info(
        "Captions extracted for job %s: source=%s, length=%d chars, language=%s",
        job_id,
        caption_source,
        len(raw_transcript),
        language,
    )

    return CaptionResult(
        raw_transcript=raw_transcript,
        cleaned_transcript=cleaned_transcript,
        caption_source=caption_source,
        metadata=metadata,
        language=language,
    )


def _extract_info(url: str, output_dir: str) -> dict:
    """Extract video info without downloading."""
    opts = {
        "outtmpl": f"{output_dir}/%(id)s.%(ext)s",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": settings.download_timeout_seconds,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise CaptionExtractionError(
            f"Failed to extract video info: {e}",
            code="INFO_EXTRACTION_FAILED",
        ) from e

    if info is None:
        raise CaptionExtractionError(
            "Could not extract video information.",
            code="INFO_EXTRACTION_FAILED",
        )

    return info


def _download_subtitles(url: str, output_dir: str) -> None:
    """Download subtitle files without downloading the video."""
    subtitle_langs = settings.subtitle_langs.split(",")
    opts = {
        "outtmpl": f"{output_dir}/subs",
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": subtitle_langs,
        "subtitlesformat": settings.subtitle_format,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": settings.download_timeout_seconds,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError:
        # Subtitle download failure is non-fatal — we fall back to description
        logger.warning("Subtitle download failed for %s, will use description", url)


def _find_subtitle_file(output_dir: str) -> tuple[str | None, str]:
    """
    Find the best subtitle file in the output directory.

    Returns (file_path, source_type) where source_type is "manual" or "auto".
    Manual subtitles are preferred over auto-generated ones.
    """
    output = Path(output_dir)

    # Look for manual subtitles first (files without "auto" in the name)
    for ext in ("vtt", "srt", "json3"):
        manual_files = [
            f
            for f in output.glob(f"subs.*.{ext}")
            if ".auto." not in f.name and f.stat().st_size > 0
        ]
        if manual_files:
            return str(manual_files[0]), "manual"

    # Fall back to auto-generated subtitles
    for ext in ("vtt", "srt", "json3"):
        auto_files = [f for f in output.glob(f"subs*.{ext}") if f.stat().st_size > 0]
        if auto_files:
            return str(auto_files[0]), "auto"

    return None, "description_only"


def _parse_subtitles(file_path: str) -> str:
    """
    Parse VTT or SRT subtitle file into plain text.

    Handles: timestamp removal, HTML tag stripping, duplicate line deduplication
    (common in auto-generated captions with overlapping segments).
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")

    # Remove VTT header and metadata
    content = _VTT_HEADER_PATTERN.sub("", content)
    content = _VTT_META_PATTERN.sub("", content)

    # Remove timestamp lines
    content = _TIMESTAMP_PATTERN.sub("", content)

    # Remove SRT sequence numbers
    content = _SRT_SEQUENCE_PATTERN.sub("", content)

    # Remove HTML tags (e.g., <c>, </c>, <b>, etc.)
    content = _HTML_TAG_PATTERN.sub("", content)

    # Split into lines, strip, remove empty lines, deduplicate consecutive lines
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)

    return " ".join(deduped)


def _extract_metadata(info: dict) -> dict:
    """Extract relevant metadata from yt-dlp info dict."""
    # Parse hashtags from description or tags
    tags = info.get("tags") or []
    description = info.get("description") or ""
    hashtags = [t for t in tags if isinstance(t, str)]
    # Also extract hashtags from description
    hashtags.extend(re.findall(r"#(\w+)", description))
    hashtags = list(dict.fromkeys(hashtags))  # deduplicate preserving order

    return {
        "duration_seconds": info.get("duration"),
        "creator_handle": info.get("uploader") or info.get("channel"),
        "caption": info.get("description") or info.get("title"),
        "title": info.get("title"),
        "description": description,
        "hashtags": hashtags,
        "thumbnail_url": info.get("thumbnail"),
    }


def _detect_language(info: dict, caption_source: str) -> str | None:
    """Detect language from subtitle metadata."""
    if caption_source == "description_only":
        return None

    # Try to get language from subtitle info
    subs = info.get("subtitles") or {}
    auto_subs = info.get("automatic_captions") or {}

    # Check manual subtitles first
    if subs:
        return next(iter(subs.keys()), None)
    if auto_subs:
        return next(iter(auto_subs.keys()), None)

    return None


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
