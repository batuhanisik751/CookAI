from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yt_dlp

from app.services.video_downloader import (
    DownloadResult,
    VideoDownloadError,
    VideoDurationExceededError,
    download_video,
)


@pytest.fixture
def fake_video(tmp_media_dir, sample_job_id):
    """Create a fake video file in the expected output dir."""
    job_dir = Path(tmp_media_dir) / sample_job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    video_file = job_dir / "video.mp4"
    video_file.write_bytes(b"fake video data")
    return str(video_file)


def _mock_settings(mock, tmp_media_dir):
    mock.temp_media_dir = tmp_media_dir
    mock.download_timeout_seconds = 60
    mock.max_download_retries = 3
    mock.max_video_duration_seconds = 300


class TestDownloadVideo:
    @patch("app.services.video_downloader.settings")
    @patch("app.services.video_downloader.yt_dlp.YoutubeDL")
    def test_successful_download(
        self,
        mock_ydl_class,
        mock_settings,
        tmp_media_dir,
        sample_job_id,
    ):
        _mock_settings(mock_settings, tmp_media_dir)

        info_instance = MagicMock()
        info_instance.extract_info.return_value = {
            "duration": 30,
            "width": 1080,
            "height": 1920,
            "uploader": "chef",
            "description": "recipe",
            "thumbnail": "https://example.com/thumb.jpg",
        }

        download_instance = MagicMock()

        def create_fake_video(urls):
            job_dir = Path(tmp_media_dir) / sample_job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            (job_dir / "video.mp4").write_bytes(b"fake")

        download_instance.download.side_effect = create_fake_video

        mock_ydl_class.return_value.__enter__ = MagicMock(
            side_effect=[info_instance, download_instance]
        )
        mock_ydl_class.return_value.__exit__ = MagicMock(
            return_value=False,
        )

        url = "https://www.tiktok.com/@user/video/123"
        result = download_video(url, sample_job_id)
        assert isinstance(result, DownloadResult)
        assert result.video_path.endswith(".mp4")
        assert result.metadata["creator_handle"] == "chef"

    @patch("app.services.video_downloader.settings")
    @patch("app.services.video_downloader.yt_dlp.YoutubeDL")
    def test_duration_exceeded(
        self,
        mock_ydl_class,
        mock_settings,
        tmp_media_dir,
        sample_job_id,
    ):
        _mock_settings(mock_settings, tmp_media_dir)

        info_instance = MagicMock()
        info_instance.extract_info.return_value = {"duration": 600}

        mock_ydl_class.return_value.__enter__ = MagicMock(
            return_value=info_instance,
        )
        mock_ydl_class.return_value.__exit__ = MagicMock(
            return_value=False,
        )

        url = "https://www.tiktok.com/@user/video/123"
        with pytest.raises(VideoDurationExceededError):
            download_video(url, sample_job_id)

    @patch("app.services.video_downloader.settings")
    @patch("app.services.video_downloader.yt_dlp.YoutubeDL")
    def test_info_extraction_failure(
        self,
        mock_ydl_class,
        mock_settings,
        tmp_media_dir,
        sample_job_id,
    ):
        _mock_settings(mock_settings, tmp_media_dir)

        info_instance = MagicMock()
        info_instance.extract_info.side_effect = yt_dlp.utils.DownloadError("not found")

        mock_ydl_class.return_value.__enter__ = MagicMock(
            return_value=info_instance,
        )
        mock_ydl_class.return_value.__exit__ = MagicMock(
            return_value=False,
        )

        url = "https://www.tiktok.com/@user/video/123"
        with pytest.raises(VideoDownloadError) as exc_info:
            download_video(url, sample_job_id)
        assert exc_info.value.code == "INFO_EXTRACTION_FAILED"

    @patch("app.services.video_downloader.time.sleep")
    @patch("app.services.video_downloader.settings")
    @patch("app.services.video_downloader.yt_dlp.YoutubeDL")
    def test_retry_on_download_failure(
        self,
        mock_ydl_class,
        mock_settings,
        mock_sleep,
        tmp_media_dir,
        sample_job_id,
    ):
        _mock_settings(mock_settings, tmp_media_dir)

        info_instance = MagicMock()
        info_instance.extract_info.return_value = {"duration": 30}

        download_instance = MagicMock()
        download_instance.download.side_effect = yt_dlp.utils.DownloadError(
            "network error"
        )

        mock_ydl_class.return_value.__enter__ = MagicMock(
            side_effect=[
                info_instance,
                download_instance,
                download_instance,
                download_instance,
            ]
        )
        mock_ydl_class.return_value.__exit__ = MagicMock(
            return_value=False,
        )

        url = "https://www.tiktok.com/@user/video/123"
        with pytest.raises(VideoDownloadError) as exc_info:
            download_video(url, sample_job_id)
        assert exc_info.value.code == "DOWNLOAD_FAILED"
        assert mock_sleep.call_count == 2

    @patch("app.services.video_downloader.settings")
    @patch("app.services.video_downloader.yt_dlp.YoutubeDL")
    def test_none_info_returns_error(
        self,
        mock_ydl_class,
        mock_settings,
        tmp_media_dir,
        sample_job_id,
    ):
        _mock_settings(mock_settings, tmp_media_dir)

        info_instance = MagicMock()
        info_instance.extract_info.return_value = None

        mock_ydl_class.return_value.__enter__ = MagicMock(
            return_value=info_instance,
        )
        mock_ydl_class.return_value.__exit__ = MagicMock(
            return_value=False,
        )

        url = "https://www.tiktok.com/@user/video/123"
        with pytest.raises(VideoDownloadError) as exc_info:
            download_video(url, sample_job_id)
        assert exc_info.value.code == "INFO_EXTRACTION_FAILED"
