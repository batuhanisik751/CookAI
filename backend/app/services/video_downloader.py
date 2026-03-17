import logging
import time
from dataclasses import dataclass
from pathlib import Path

import yt_dlp

from app.core.config import settings

logger = logging.getLogger(__name__)


class VideoDownloadError(Exception):
    """Raised when video download fails."""

    def __init__(self, message: str, code: str = "DOWNLOAD_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


class VideoDurationExceededError(VideoDownloadError):
    """Raised when video exceeds max duration."""

    def __init__(self, duration: float, max_duration: int):
        super().__init__(
            f"Video duration ({duration:.0f}s) exceeds limit ({max_duration}s).",
            code="DURATION_EXCEEDED",
        )


@dataclass
class DownloadResult:
    video_path: str
    metadata: dict


def _get_ytdlp_options(output_dir: str) -> dict:
    """Build yt-dlp options dict."""
    return {
        "outtmpl": f"{output_dir}/video.%(ext)s",
        "format": "best[ext=mp4]/best",
        "socket_timeout": settings.download_timeout_seconds,
        "retries": 0,  # We handle retries ourselves
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": False,
        "noplaylist": True,
        "max_filesize": 100 * 1024 * 1024,  # 100MB
    }


def _extract_metadata(info: dict) -> dict:
    """Extract relevant metadata from yt-dlp info dict."""
    return {
        "duration_seconds": info.get("duration"),
        "resolution": (
            f"{info.get('width', '?')}x{info.get('height', '?')}"
            if info.get("width")
            else None
        ),
        "creator_handle": info.get("uploader") or info.get("channel"),
        "caption": info.get("description") or info.get("title"),
        "thumbnail_url": info.get("thumbnail"),
    }


def download_video(url: str, job_id: str) -> DownloadResult:
    """
    Download a video using yt-dlp with retry logic.

    This is a synchronous function designed to run in Celery workers.

    Args:
        url: Pre-validated video URL.
        job_id: UUID string for organizing output files.

    Returns:
        DownloadResult with video path and metadata.

    Raises:
        VideoDownloadError: On download failure after retries.
        VideoDurationExceeded: If video exceeds max duration.
    """
    output_dir = str(Path(settings.temp_media_dir) / job_id)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    opts = _get_ytdlp_options(output_dir)

    # Step 1: Extract info without downloading to check duration
    try:
        with yt_dlp.YoutubeDL({**opts, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise VideoDownloadError(
            f"Failed to extract video info: {e}",
            code="INFO_EXTRACTION_FAILED",
        ) from e

    if info is None:
        raise VideoDownloadError(
            "Could not extract video information.",
            code="INFO_EXTRACTION_FAILED",
        )

    duration = info.get("duration")
    if duration and duration > settings.max_video_duration_seconds:
        raise VideoDurationExceededError(
            duration,
            settings.max_video_duration_seconds,
        )

    # Step 2: Download with retry logic
    last_error = None
    for attempt in range(1, settings.max_download_retries + 1):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            break
        except yt_dlp.utils.DownloadError as e:
            last_error = e
            logger.warning(
                "Download attempt %d/%d failed for job %s: %s",
                attempt,
                settings.max_download_retries,
                job_id,
                e,
            )
            if attempt < settings.max_download_retries:
                backoff = 2**attempt
                time.sleep(backoff)
    else:
        retries = settings.max_download_retries
        raise VideoDownloadError(
            f"Download failed after {retries} attempts: {last_error}",
            code="DOWNLOAD_FAILED",
        ) from last_error

    # Step 3: Find the downloaded video file
    video_files = list(Path(output_dir).glob("video.*"))
    if not video_files:
        raise VideoDownloadError(
            "Download completed but no video file found.",
            code="FILE_NOT_FOUND",
        )

    video_path = str(video_files[0])
    metadata = _extract_metadata(info)

    logger.info("Downloaded video for job %s: %s", job_id, video_path)
    return DownloadResult(video_path=video_path, metadata=metadata)
