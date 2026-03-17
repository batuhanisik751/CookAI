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
from app.services.caption_extractor import CaptionExtractionError, CaptionResult
from app.services.url_validator import ValidationResult

TIKTOK_URL = "https://www.tiktok.com/@user/video/123"


def _make_session_ctx(sync_db_session):
    """Create a mock context manager that returns the test session."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=sync_db_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return mock_ctx


def _make_caption_result():
    return CaptionResult(
        raw_transcript="Add one cup of flour and two eggs",
        cleaned_transcript="Add 1 cup of flour and two eggs",
        caption_source="auto",
        metadata={
            "duration_seconds": 30,
            "creator_handle": "user",
            "caption": "Easy recipe",
            "title": "Easy recipe",
            "description": "Easy recipe",
            "hashtags": ["cooking"],
            "thumbnail_url": None,
        },
        language="en",
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
    @patch("app.workers.tasks.extract_captions")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_happy_path(
        self,
        mock_get_session,
        mock_validate,
        mock_extract_captions,
        mock_synthesize,
        sync_db_session,
        job_in_db,
    ):
        """Test the full pipeline succeeds through all 4 stages."""
        from app.workers.tasks import process_video

        mock_get_session.return_value = _make_session_ctx(sync_db_session)

        mock_validate.return_value = ValidationResult(
            is_valid=True,
            platform="tiktok",
            normalized_url=TIKTOK_URL,
        )

        mock_extract_captions.return_value = _make_caption_result()
        mock_synthesize.return_value = _make_synthesis_result()

        result = process_video(job_in_db)
        assert result["status"] == "complete"

        # Verify all stages were called
        mock_validate.assert_called_once()
        mock_extract_captions.assert_called_once()
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

    @patch("app.workers.tasks.extract_captions")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_caption_extraction_failure(
        self,
        mock_get_session,
        mock_validate,
        mock_extract_captions,
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

        mock_extract_captions.side_effect = CaptionExtractionError(
            "No captions available",
            "NO_TRANSCRIPT_AVAILABLE",
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"
        assert "No captions" in result["error"]

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

    @patch("app.workers.tasks.synthesize_recipe")
    @patch("app.workers.tasks.extract_captions")
    @patch("app.workers.tasks.validate_url")
    @patch("app.workers.tasks.get_sync_session")
    def test_synthesis_failure(
        self,
        mock_get_session,
        mock_validate,
        mock_extract_captions,
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
        mock_extract_captions.return_value = _make_caption_result()

        mock_synthesize.side_effect = RecipeSynthesisError(
            "Parse error", code="SYNTHESIS_PARSE_ERROR"
        )

        result = process_video(job_in_db)
        assert result["status"] == "failed"
        assert "Parse error" in result["error"]
