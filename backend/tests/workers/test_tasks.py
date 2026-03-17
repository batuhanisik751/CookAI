import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.job import ProcessingJob
from app.schemas.recipe import (
    ConfidenceScores,
    IngredientSchema,
    LLMRecipeOutput,
    StepSchema,
)
from app.services.url_validator import ValidationResult
from app.services.video_downloader import (
    DownloadResult,
    VideoDownloadError,
)

TIKTOK_URL = "https://www.tiktok.com/@user/video/123"


def _make_session_ctx(sync_db_session):
    """Create a mock context manager that returns the test session."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=sync_db_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


def _make_transcription_result():
    from app.services.transcription import TranscriptionResult

    return TranscriptionResult(
        raw_transcript="Add one cup of flour and two eggs",
        cleaned_transcript="Add 1 cup of flour and two eggs",
        language="en",
        duration_seconds=30.0,
    )


def _make_visual_analysis():
    from app.services.visual_analyzer import VisualAnalysis

    return VisualAnalysis(
        ingredients_observed=["flour", "eggs"],
        techniques_observed=["mixing"],
        equipment_observed=["bowl"],
        plating_notes=None,
        frame_observations=[],
    )


def _make_synthesis_result():
    from app.services.recipe_synthesizer import SynthesisResult

    return SynthesisResult(
        recipe_data=LLMRecipeOutput(
            title="Simple Recipe",
            servings=2,
            prep_time_minutes=5,
            cook_time_minutes=10,
            difficulty="easy",
            cuisine_tags=["American"],
            ingredients=[
                IngredientSchema(name="flour", quantity="1", unit="cup", order_index=0),
                IngredientSchema(name="eggs", quantity="2", unit=None, order_index=1),
            ],
            steps=[
                StepSchema(
                    step_number=1,
                    instruction="Mix flour and eggs.",
                ),
            ],
            confidence=ConfidenceScores(),
        ),
        needs_review=False,
        review_flags=[],
    )


class TestProcessVideoTask:
    @pytest.fixture
    def job_in_db(self, sync_db_session):
        """Create a pending job in the test database."""
        job_id = uuid.uuid4()
        job = ProcessingJob(
            id=job_id,
            source_url=TIKTOK_URL,
            normalized_url=TIKTOK_URL,
            platform="tiktok",
            status="pending",
        )
        sync_db_session.add(job)
        sync_db_session.commit()
        return str(job_id)

    @patch("app.workers.tasks.synthesize_recipe")
    @patch("app.workers.tasks.analyze_frames")
    @patch("app.workers.tasks.transcribe_audio")
    @patch("app.workers.tasks.extract_frames")
    @patch("app.workers.tasks.extract_audio")
    @patch("app.workers.tasks.download_video")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_happy_path(
        self,
        mock_get_session,
        mock_validate,
        mock_download,
        mock_extract_audio,
        mock_extract_frames,
        mock_transcribe,
        mock_analyze,
        mock_synthesize,
        sync_db_session,
        job_in_db,
    ):
        """Test the full pipeline succeeds through all 8 stages."""
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=True,
            platform="tiktok",
            normalized_url=TIKTOK_URL,
        )

        mock_download.return_value = DownloadResult(
            video_path="/tmp/media/test/video.mp4",
            metadata={
                "duration_seconds": 30,
                "creator_handle": "user",
            },
        )

        mock_extract_audio.return_value = "/tmp/media/test/audio.wav"
        mock_extract_frames.return_value = ["/tmp/media/test/frames/frame_0001.jpg"]

        mock_transcribe.return_value = _make_transcription_result()
        mock_analyze.return_value = _make_visual_analysis()
        mock_synthesize.return_value = _make_synthesis_result()

        result = process_video(job_in_db)
        assert result["status"] == "complete"

        # Verify all stages were called
        mock_validate.assert_called_once()
        mock_download.assert_called_once()
        mock_extract_audio.assert_called_once()
        mock_extract_frames.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_analyze.assert_called_once()
        mock_synthesize.assert_called_once()

    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_validation_failure(
        self,
        mock_get_session,
        mock_validate,
        sync_db_session,
        job_in_db,
    ):
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=False,
            error_code="UNSUPPORTED_PLATFORM",
            error_message="URL must be from TikTok or IG.",
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"
        assert "error" in result

    @patch("app.workers.tasks.download_video")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_download_failure(
        self,
        mock_get_session,
        mock_validate,
        mock_download,
        sync_db_session,
        job_in_db,
    ):
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=True,
            platform="tiktok",
            normalized_url=TIKTOK_URL,
        )

        mock_download.side_effect = VideoDownloadError(
            "network error",
            "DOWNLOAD_FAILED",
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"

    @patch("app.workers.tasks.get_sync_session")
    def test_job_not_found(
        self,
        mock_get_session,
        sync_db_session,
    ):
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        result = process_video(str(uuid.uuid4()))
        assert result["status"] == "failed"
        assert "not found" in result["error"].lower()

    @patch("app.workers.tasks.transcribe_audio")
    @patch("app.workers.tasks.extract_frames")
    @patch("app.workers.tasks.extract_audio")
    @patch("app.workers.tasks.download_video")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_transcription_failure(
        self,
        mock_get_session,
        mock_validate,
        mock_download,
        mock_extract_audio,
        mock_extract_frames,
        mock_transcribe,
        sync_db_session,
        job_in_db,
    ):
        from app.services.transcription import TranscriptionError
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=True, platform="tiktok", normalized_url=TIKTOK_URL
        )
        mock_download.return_value = DownloadResult(
            video_path="/tmp/media/test/video.mp4",
            metadata={"duration_seconds": 30, "creator_handle": "user"},
        )
        mock_extract_audio.return_value = "/tmp/media/test/audio.wav"
        mock_extract_frames.return_value = ["/tmp/media/test/frames/frame_0001.jpg"]

        mock_transcribe.side_effect = TranscriptionError(
            "API error", code="TRANSCRIPTION_API_ERROR"
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"
        assert "API error" in result["error"]

    @patch("app.workers.tasks.analyze_frames")
    @patch("app.workers.tasks.transcribe_audio")
    @patch("app.workers.tasks.extract_frames")
    @patch("app.workers.tasks.extract_audio")
    @patch("app.workers.tasks.download_video")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_visual_analysis_failure(
        self,
        mock_get_session,
        mock_validate,
        mock_download,
        mock_extract_audio,
        mock_extract_frames,
        mock_transcribe,
        mock_analyze,
        sync_db_session,
        job_in_db,
    ):
        from app.services.visual_analyzer import VisualAnalysisError
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=True, platform="tiktok", normalized_url=TIKTOK_URL
        )
        mock_download.return_value = DownloadResult(
            video_path="/tmp/media/test/video.mp4",
            metadata={"duration_seconds": 30, "creator_handle": "user"},
        )
        mock_extract_audio.return_value = "/tmp/media/test/audio.wav"
        mock_extract_frames.return_value = ["/tmp/media/test/frames/frame_0001.jpg"]
        mock_transcribe.return_value = _make_transcription_result()

        mock_analyze.side_effect = VisualAnalysisError(
            "Vision API error", code="VISION_API_ERROR"
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"
        assert "Vision API error" in result["error"]

    @patch("app.workers.tasks.synthesize_recipe")
    @patch("app.workers.tasks.analyze_frames")
    @patch("app.workers.tasks.transcribe_audio")
    @patch("app.workers.tasks.extract_frames")
    @patch("app.workers.tasks.extract_audio")
    @patch("app.workers.tasks.download_video")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_synthesis_failure(
        self,
        mock_get_session,
        mock_validate,
        mock_download,
        mock_extract_audio,
        mock_extract_frames,
        mock_transcribe,
        mock_analyze,
        mock_synthesize,
        sync_db_session,
        job_in_db,
    ):
        from app.services.recipe_synthesizer import RecipeSynthesisError
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=True, platform="tiktok", normalized_url=TIKTOK_URL
        )
        mock_download.return_value = DownloadResult(
            video_path="/tmp/media/test/video.mp4",
            metadata={"duration_seconds": 30, "creator_handle": "user"},
        )
        mock_extract_audio.return_value = "/tmp/media/test/audio.wav"
        mock_extract_frames.return_value = ["/tmp/media/test/frames/frame_0001.jpg"]
        mock_transcribe.return_value = _make_transcription_result()
        mock_analyze.return_value = _make_visual_analysis()

        mock_synthesize.side_effect = RecipeSynthesisError(
            "Parse error", code="SYNTHESIS_PARSE_ERROR"
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"
        assert "Parse error" in result["error"]
