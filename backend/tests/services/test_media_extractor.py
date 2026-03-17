import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.media_extractor import (
    MediaExtractionError,
    _validate_path,
    extract_audio,
    extract_frames,
    extract_metadata,
)


@pytest.fixture
def video_setup(tmp_media_dir):
    """Create a fake video file and output directory."""
    job_dir = Path(tmp_media_dir) / "test-job"
    job_dir.mkdir(parents=True, exist_ok=True)
    video_file = job_dir / "video.mp4"
    video_file.write_bytes(b"fake video data")
    return str(video_file), str(job_dir)


class TestValidatePath:
    @patch("app.services.media_extractor.settings")
    def test_valid_path(self, mock_settings, tmp_media_dir):
        mock_settings.temp_media_dir = tmp_media_dir
        path = Path(tmp_media_dir) / "job" / "video.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        result = _validate_path(str(path))
        assert str(result).startswith(str(Path(tmp_media_dir).resolve()))

    @patch("app.services.media_extractor.settings")
    def test_path_traversal_rejected(
        self,
        mock_settings,
        tmp_media_dir,
    ):
        mock_settings.temp_media_dir = tmp_media_dir
        with pytest.raises(MediaExtractionError) as exc_info:
            _validate_path("/etc/passwd")
        assert exc_info.value.code == "INVALID_PATH"


class TestExtractAudio:
    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_audio_success(
        self,
        mock_subprocess,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)
        mock_settings.audio_sample_rate = 16000

        process = AsyncMock()
        process.communicate.return_value = (b"", b"")
        process.returncode = 0
        mock_subprocess.return_value = process

        result = await extract_audio(video_path, output_dir)
        assert result.endswith("audio.wav")
        mock_subprocess.assert_called_once()
        cmd = mock_subprocess.call_args[0]
        assert "ffmpeg" in cmd[0]
        assert "-ar" in cmd
        assert "16000" in cmd

    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_audio_ffmpeg_failure(
        self,
        mock_subprocess,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)
        mock_settings.audio_sample_rate = 16000

        process = AsyncMock()
        process.communicate.return_value = (
            b"",
            b"Error: no audio stream",
        )
        process.returncode = 1
        mock_subprocess.return_value = process

        with pytest.raises(MediaExtractionError) as exc_info:
            await extract_audio(video_path, output_dir)
        assert exc_info.value.code == "SUBPROCESS_FAILED"


class TestExtractFrames:
    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_frames_success(
        self,
        mock_subprocess,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)
        mock_settings.frame_extraction_fps = 1

        process = AsyncMock()
        process.communicate.return_value = (b"", b"")
        process.returncode = 0
        mock_subprocess.return_value = process

        frames_dir = Path(output_dir) / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            (frames_dir / f"frame_{i:04d}.jpg").write_bytes(b"fake frame")

        result = await extract_frames(video_path, output_dir)
        assert len(result) == 5
        assert all(p.endswith(".jpg") for p in result)

    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_frames_custom_fps(
        self,
        mock_subprocess,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)
        mock_settings.frame_extraction_fps = 1

        process = AsyncMock()
        process.communicate.return_value = (b"", b"")
        process.returncode = 0
        mock_subprocess.return_value = process

        frames_dir = Path(output_dir) / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        await extract_frames(video_path, output_dir, fps=2)
        cmd = mock_subprocess.call_args[0]
        assert "fps=2" in cmd[4]


class TestExtractMetadata:
    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_metadata_success(
        self,
        mock_subprocess,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)

        probe_output = json.dumps(
            {
                "format": {
                    "duration": "30.5",
                    "format_name": "mov,mp4",
                    "size": "5242880",
                },
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1080,
                        "height": 1920,
                    }
                ],
            }
        )

        process = AsyncMock()
        process.communicate.return_value = (
            probe_output.encode(),
            b"",
        )
        process.returncode = 0
        mock_subprocess.return_value = process

        result = await extract_metadata(video_path)
        assert result["duration_seconds"] == 30.5
        assert result["resolution"] == "1080x1920"
        assert result["codec"] == "h264"

    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_metadata_parse_error(
        self,
        mock_subprocess,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)

        process = AsyncMock()
        process.communicate.return_value = (b"not json", b"")
        process.returncode = 0
        mock_subprocess.return_value = process

        with pytest.raises(MediaExtractionError) as exc_info:
            await extract_metadata(video_path)
        assert exc_info.value.code == "METADATA_PARSE_FAILED"

    @pytest.mark.asyncio
    @patch("app.services.media_extractor.settings")
    @patch("app.services.media_extractor.asyncio.wait_for")
    @patch("app.services.media_extractor.asyncio.create_subprocess_exec")
    async def test_extract_metadata_timeout(
        self,
        mock_subprocess,
        mock_wait_for,
        mock_settings,
        video_setup,
    ):
        video_path, output_dir = video_setup
        mock_settings.temp_media_dir = str(Path(output_dir).parent)

        process = AsyncMock()
        process.kill = MagicMock()
        process.communicate.return_value = (b"", b"")
        mock_subprocess.return_value = process

        mock_wait_for.side_effect = TimeoutError()

        with pytest.raises(MediaExtractionError) as exc_info:
            await extract_metadata(video_path)
        assert exc_info.value.code == "EXTRACTION_TIMEOUT"
