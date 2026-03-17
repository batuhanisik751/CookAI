import asyncio
import logging
import uuid as uuid_mod
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import get_sync_session
from app.models.job import ProcessingJob
from app.models.recipe import Ingredient, Recipe, Step
from app.services.cleanup import cleanup_expired_media
from app.services.media_extractor import extract_audio, extract_frames
from app.services.recipe_synthesizer import RecipeSynthesisError, synthesize_recipe
from app.services.transcription import TranscriptionError, transcribe_audio
from app.services.url_validator import validate_url
from app.services.video_downloader import (
    VideoDownloadError,
    download_video,
)
from app.services.visual_analyzer import VisualAnalysisError, analyze_frames
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_job_status(
    job_id: str,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
    metadata_json: dict | None = None,
    media_dir: str | None = None,
) -> None:
    """Update a job's status in the database."""
    pk = uuid_mod.UUID(job_id) if isinstance(job_id, str) else job_id
    with get_sync_session() as session:
        job = session.get(ProcessingJob, pk)
        if job is None:
            logger.error("Job %s not found in database", job_id)
            return
        job.status = status
        if error_code:
            job.error_code = error_code
            job.error_message = error_message
        if metadata_json:
            job.metadata_json = metadata_json
        if media_dir:
            job.media_dir = media_dir
        if status == "downloading":
            job.started_at = datetime.now(UTC)
        if status in ("complete", "failed"):
            job.completed_at = datetime.now(UTC)


@celery_app.task(name="app.workers.tasks.process_video", bind=True)
def process_video(self, job_id: str) -> dict:
    """
    Main video processing pipeline task.

    Pipeline stages:
    1. Validate URL
    2. Check cache (existing completed job with same normalized URL)
    3. Download video
    4. Extract audio and frames
    5. Transcribe audio (Whisper)
    6. Analyze frames (Claude vision)
    7. Synthesize recipe (Claude)
    8. Mark complete
    """
    logger.info("Starting video processing for job %s", job_id)
    pk = uuid_mod.UUID(job_id) if isinstance(job_id, str) else job_id

    # Store celery task ID
    with get_sync_session() as session:
        job = session.get(ProcessingJob, pk)
        if job is None:
            logger.error("Job %s not found", job_id)
            return {"status": "failed", "error": "Job not found"}
        job.celery_task_id = self.request.id
        source_url = job.source_url

    # Stage 1: Validate URL
    _update_job_status(job_id, "validating")
    try:
        result = asyncio.get_event_loop().run_until_complete(validate_url(source_url))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(validate_url(source_url))
        finally:
            loop.close()

    if not result.is_valid:
        _update_job_status(
            job_id,
            "failed",
            error_code=result.error_code,
            error_message=result.error_message,
        )
        return {"status": "failed", "error": result.error_message}

    # Update normalized URL and platform
    with get_sync_session() as session:
        job = session.get(ProcessingJob, pk)
        if job:
            job.normalized_url = result.normalized_url
            job.platform = result.platform

    # Stage 2: Check cache
    with get_sync_session() as session:
        existing = session.execute(
            select(ProcessingJob).where(
                ProcessingJob.normalized_url == result.normalized_url,
                ProcessingJob.status == "complete",
                ProcessingJob.id != pk,
            )
        ).scalar_one_or_none()

        if existing:
            logger.info("Cache hit for job %s — reusing job %s", job_id, existing.id)
            _update_job_status(
                job_id,
                "complete",
                metadata_json=existing.metadata_json,
                media_dir=existing.media_dir,
            )
            return {
                "status": "complete",
                "cached": True,
                "source_job": str(existing.id),
            }

    # Stage 3: Download video
    _update_job_status(job_id, "downloading")
    try:
        download_result = download_video(result.normalized_url, job_id)
    except VideoDownloadError as e:
        _update_job_status(job_id, "failed", error_code=e.code, error_message=e.message)
        return {"status": "failed", "error": e.message}

    # Stage 4: Extract media
    _update_job_status(job_id, "extracting")
    try:
        output_dir = str(download_result.video_path).rsplit("/", 1)[0]

        # Run async FFmpeg operations
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            audio_path = loop.run_until_complete(
                extract_audio(download_result.video_path, output_dir)
            )
            frame_paths = loop.run_until_complete(
                extract_frames(download_result.video_path, output_dir)
            )
        finally:
            if loop != asyncio.get_event_loop():
                loop.close()

        metadata = {
            **download_result.metadata,
            "audio_path": audio_path,
            "frame_count": len(frame_paths),
            "frame_paths": frame_paths,
        }
    except Exception as e:
        logger.exception("Media extraction failed for job %s", job_id)
        _update_job_status(
            job_id,
            "failed",
            error_code="EXTRACTION_FAILED",
            error_message=str(e),
        )
        return {"status": "failed", "error": str(e)}

    # Save media metadata to DB before AI stages
    _update_job_status(
        job_id, "extracting", metadata_json=metadata, media_dir=output_dir
    )

    # Stage 5: Transcribe audio
    _update_job_status(job_id, "transcribing")
    try:
        transcription = transcribe_audio(metadata["audio_path"])
        metadata["raw_transcript"] = transcription.raw_transcript
        metadata["cleaned_transcript"] = transcription.cleaned_transcript
        metadata["language"] = transcription.language
        metadata["transcription_duration"] = transcription.duration_seconds
    except TranscriptionError as e:
        logger.exception("Transcription failed for job %s", job_id)
        _update_job_status(job_id, "failed", error_code=e.code, error_message=e.message)
        return {"status": "failed", "error": e.message}

    # Stage 6: Analyze frames
    _update_job_status(job_id, "analyzing")
    try:
        visual_analysis = analyze_frames(metadata.get("frame_paths", []))
        metadata["visual_analysis"] = {
            "ingredients_observed": visual_analysis.ingredients_observed,
            "techniques_observed": visual_analysis.techniques_observed,
            "equipment_observed": visual_analysis.equipment_observed,
            "plating_notes": visual_analysis.plating_notes,
            "frame_observations": visual_analysis.frame_observations,
        }
    except VisualAnalysisError as e:
        logger.exception("Visual analysis failed for job %s", job_id)
        _update_job_status(job_id, "failed", error_code=e.code, error_message=e.message)
        return {"status": "failed", "error": e.message}

    # Stage 7: Synthesize recipe
    _update_job_status(job_id, "synthesizing")
    try:
        synthesis = synthesize_recipe(
            transcript=metadata["cleaned_transcript"],
            visual_analysis=visual_analysis,
            metadata=metadata,
        )

        # Store recipe in database
        with get_sync_session() as session:
            job = session.get(ProcessingJob, pk)
            recipe = Recipe(
                job_id=pk,
                source_url=job.source_url,
                platform=job.platform,
                title=synthesis.recipe_data.title,
                servings=synthesis.recipe_data.servings,
                prep_time_minutes=synthesis.recipe_data.prep_time_minutes,
                cook_time_minutes=synthesis.recipe_data.cook_time_minutes,
                difficulty=synthesis.recipe_data.difficulty,
                cuisine_tags=synthesis.recipe_data.cuisine_tags,
                language=metadata.get("language"),
                raw_transcript=metadata.get("raw_transcript"),
                cleaned_transcript=metadata.get("cleaned_transcript"),
                visual_analysis=metadata.get("visual_analysis"),
                confidence=synthesis.recipe_data.confidence.model_dump(),
                needs_review=synthesis.needs_review,
                review_flags=synthesis.review_flags,
            )
            session.add(recipe)
            session.flush()

            for ing in synthesis.recipe_data.ingredients:
                session.add(
                    Ingredient(
                        recipe_id=recipe.id,
                        name=ing.name,
                        quantity=ing.quantity,
                        unit=ing.unit,
                        order_index=ing.order_index,
                        notes=ing.notes,
                        confidence=ing.confidence,
                    )
                )

            for step in synthesis.recipe_data.steps:
                session.add(
                    Step(
                        recipe_id=recipe.id,
                        step_number=step.step_number,
                        instruction=step.instruction,
                        duration_estimate=step.duration_estimate,
                        tip=step.tip,
                        confidence=step.confidence,
                    )
                )

            metadata["recipe_id"] = str(recipe.id)

    except RecipeSynthesisError as e:
        logger.exception("Recipe synthesis failed for job %s", job_id)
        _update_job_status(job_id, "failed", error_code=e.code, error_message=e.message)
        return {"status": "failed", "error": e.message}

    # Stage 8: Complete
    _update_job_status(
        job_id,
        "complete",
        metadata_json=metadata,
        media_dir=output_dir,
    )
    logger.info("Video processing complete for job %s", job_id)
    return {"status": "complete", "job_id": job_id}


@celery_app.task(name="app.workers.tasks.cleanup_expired_media_task")
def cleanup_expired_media_task() -> dict:
    """Periodic task to clean up expired media files."""
    removed = cleanup_expired_media()
    return {"removed_count": removed}
