import time
from pathlib import Path
from unittest.mock import patch

from app.services.cleanup import cleanup_expired_media, cleanup_job_media


class TestCleanupJobMedia:
    @patch("app.services.cleanup.settings")
    def test_cleanup_existing_dir(self, mock_settings, tmp_media_dir):
        mock_settings.temp_media_dir = tmp_media_dir
        job_dir = Path(tmp_media_dir) / "test-job"
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "video.mp4").write_bytes(b"fake")
        (job_dir / "audio.wav").write_bytes(b"fake")

        result = cleanup_job_media("test-job", str(job_dir))
        assert result is True
        assert not job_dir.exists()

    @patch("app.services.cleanup.settings")
    def test_cleanup_nonexistent_dir(self, mock_settings, tmp_media_dir):
        mock_settings.temp_media_dir = tmp_media_dir
        result = cleanup_job_media("test-job", str(Path(tmp_media_dir) / "nonexistent"))
        assert result is True

    @patch("app.services.cleanup.settings")
    def test_cleanup_outside_media_dir(
        self,
        mock_settings,
        tmp_media_dir,
        tmp_path,
    ):
        mock_settings.temp_media_dir = tmp_media_dir
        # Create a real directory outside media dir
        outside = tmp_path / "outside-dir"
        outside.mkdir()
        (outside / "file.txt").write_bytes(b"data")
        result = cleanup_job_media("test-job", str(outside))
        assert result is False
        # Directory should still exist (not deleted)
        assert outside.exists()


class TestCleanupExpiredMedia:
    @patch("app.services.cleanup.get_sync_session")
    @patch("app.services.cleanup.settings")
    def test_cleanup_old_directories(self, mock_settings, mock_session, tmp_media_dir):
        mock_settings.temp_media_dir = tmp_media_dir
        mock_settings.media_ttl_hours = 24

        # Create an "old" directory
        old_dir = Path(tmp_media_dir) / "old-job"
        old_dir.mkdir(parents=True, exist_ok=True)
        (old_dir / "video.mp4").write_bytes(b"fake")

        # Make it appear old by setting mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        import os

        os.utime(str(old_dir), (old_time, old_time))

        # Mock the session context manager
        mock_ctx = mock_session.return_value.__enter__.return_value
        mock_ctx.execute.return_value = None

        removed = cleanup_expired_media()
        assert removed == 1
        assert not old_dir.exists()

    @patch("app.services.cleanup.settings")
    def test_skip_recent_directories(self, mock_settings, tmp_media_dir):
        mock_settings.temp_media_dir = tmp_media_dir
        mock_settings.media_ttl_hours = 24

        # Create a recent directory
        recent_dir = Path(tmp_media_dir) / "recent-job"
        recent_dir.mkdir(parents=True, exist_ok=True)
        (recent_dir / "video.mp4").write_bytes(b"fake")

        removed = cleanup_expired_media()
        assert removed == 0
        assert recent_dir.exists()

    @patch("app.services.cleanup.settings")
    def test_nonexistent_media_dir(self, mock_settings, tmp_path):
        mock_settings.temp_media_dir = str(tmp_path / "nonexistent")
        mock_settings.media_ttl_hours = 24
        removed = cleanup_expired_media()
        assert removed == 0
