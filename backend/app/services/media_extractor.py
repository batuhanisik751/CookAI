import asyncio
import json
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SECONDS = 120


class MediaExtractionError(Exception):
    """Raised when media extraction fails."""

    def __init__(self, message: str, code: str = "EXTRACTION_FAILED"):
        self.message = message
        self.code = code
        super().__init__(message)


def _validate_path(path: str) -> Path:
    """Validate that a path is within the temp media directory."""
    resolved = Path(path).resolve()
    media_dir = Path(settings.temp_media_dir).resolve()
    if not str(resolved).startswith(str(media_dir)):
        raise MediaExtractionError(
            "Path is outside the allowed media directory.",
            code="INVALID_PATH",
        )
    return resolved


async def _run_subprocess(
    cmd: list[str], timeout: int = FFMPEG_TIMEOUT_SECONDS
) -> tuple[bytes, bytes]:
    """Run a subprocess with timeout and return stdout, stderr."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as e:
        process.kill()
        await process.communicate()
        raise MediaExtractionError(
            f"Subprocess timed out after {timeout}s: {' '.join(cmd[:2])}",
            code="EXTRACTION_TIMEOUT",
        ) from e

    if process.returncode != 0:
        error_msg = stderr.decode(errors="replace").strip()
        raise MediaExtractionError(
            f"Subprocess failed (code {process.returncode}): {error_msg}",
            code="SUBPROCESS_FAILED",
        )

    return stdout, stderr


async def extract_audio(video_path: str, output_dir: str) -> str:
    """
    Extract audio from video as 16kHz mono WAV (optimal for Whisper).

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save the audio file.

    Returns:
        Path to the extracted WAV file.
    """
    _validate_path(video_path)
    out_path = _validate_path(f"{output_dir}/audio.wav")

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(settings.audio_sample_rate),
        "-ac",
        "1",
        "-y",
        str(out_path),
    ]

    await _run_subprocess(cmd)
    logger.info("Extracted audio: %s", out_path)
    return str(out_path)


async def extract_frames(
    video_path: str, output_dir: str, fps: int | None = None
) -> list[str]:
    """
    Extract frames from video at the configured FPS rate.

    Args:
        video_path: Path to the video file.
        output_dir: Directory to save frame images.
        fps: Frames per second to extract. Defaults to config value.

    Returns:
        List of paths to extracted frame JPEG files.
    """
    _validate_path(video_path)
    frames_dir = Path(output_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    _validate_path(str(frames_dir))

    fps = fps or settings.frame_extraction_fps

    cmd = [
        "ffmpeg",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-y",
        str(frames_dir / "frame_%04d.jpg"),
    ]

    await _run_subprocess(cmd)

    frame_paths = sorted(str(p) for p in frames_dir.glob("frame_*.jpg"))
    logger.info("Extracted %d frames from %s", len(frame_paths), video_path)
    return frame_paths


async def extract_metadata(video_path: str) -> dict:
    """
    Extract metadata from video using ffprobe.

    Args:
        video_path: Path to the video file.

    Returns:
        Dict with duration, resolution, and codec info.
    """
    _validate_path(video_path)

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    stdout, _ = await _run_subprocess(cmd, timeout=30)

    try:
        probe_data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise MediaExtractionError(
            f"Failed to parse ffprobe output: {e}",
            code="METADATA_PARSE_FAILED",
        ) from e

    # Extract key metadata
    format_info = probe_data.get("format", {})
    video_stream = next(
        (s for s in probe_data.get("streams", []) if s.get("codec_type") == "video"),
        {},
    )

    return {
        "duration_seconds": float(format_info.get("duration", 0)),
        "resolution": (
            f"{video_stream.get('width')}x{video_stream.get('height')}"
            if video_stream.get("width")
            else None
        ),
        "codec": video_stream.get("codec_name"),
        "format_name": format_info.get("format_name"),
        "file_size_bytes": int(format_info.get("size", 0)),
    }
