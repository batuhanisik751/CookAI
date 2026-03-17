import asyncio
import logging
import uuid as uuid_mod
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.database import get_sync_session
from app.models.job import ProcessingJob
from app.models.recipe import Ingredient, Recipe, Step
from app.services.caption_extractor import CaptionExtractionError, extract_captions
from app.services.cleanup import cleanup_expired_media
from app.services.recipe_synthesizer import RecipeSynthesisError, synthesize_recipe
from app.services.url_validator import validate_url
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
        if status == "extracting":
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
    3. Extract captions and metadata (yt-dlp, no video download)
    4. Synthesize recipe (Claude)
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

    # Stage 3: Extract captions and metadata
    _update_job_status(job_id, "extracting")
    try:
        caption_result = extract_captions(result.normalized_url, job_id)
    except CaptionExtractionError as e:
        _update_job_status(job_id, "failed", error_code=e.code, error_message=e.message)
        return {"status": "failed", "error": e.message}

    metadata = {
        **caption_result.metadata,
        "raw_transcript": caption_result.raw_transcript,
        "cleaned_transcript": caption_result.cleaned_transcript,
        "caption_source": caption_result.caption_source,
        "language": caption_result.language,
    }

    # Stage 4: Synthesize recipe
    _update_job_status(job_id, "synthesizing")
    try:
        synthesis = synthesize_recipe(
            transcript=metadata["cleaned_transcript"],
            metadata=metadata,
            caption_source=caption_result.caption_source,
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
                visual_analysis=None,
                caption_source=caption_result.caption_source,
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

    # Complete
    _update_job_status(
        job_id,
        "complete",
        metadata_json=metadata,
    )
    logger.info("Video processing complete for job %s", job_id)
    return {"status": "complete", "job_id": job_id}


@celery_app.task(name="app.workers.tasks.cleanup_expired_media_task")
def cleanup_expired_media_task() -> dict:
    """Periodic task to clean up expired temporary files."""
    removed = cleanup_expired_media()
    return {"removed_count": removed}
