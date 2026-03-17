import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.job import ProcessingJob
from app.schemas.error import ErrorDetail, ErrorResponse
from app.schemas.job import JobStatusResponse, VideoMetadata, VideoURLRequest
from app.services.url_validator import detect_platform
from app.workers.tasks import process_video

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_to_response(job: ProcessingJob) -> JobStatusResponse:
    """Convert a ProcessingJob model to a response schema."""
    error = None
    if job.error_code:
        error = ErrorDetail(
            code=job.error_code,
            message=job.error_message or "Unknown error",
        )

    metadata = None
    if job.metadata_json:
        metadata = VideoMetadata(
            duration_seconds=job.metadata_json.get("duration_seconds"),
            resolution=job.metadata_json.get("resolution"),
            creator_handle=job.metadata_json.get("creator_handle"),
            caption=job.metadata_json.get("caption"),
            thumbnail_url=job.metadata_json.get("thumbnail_url"),
        )

    recipe_id = None
    if job.metadata_json and job.metadata_json.get("recipe_id"):
        recipe_id = uuid.UUID(job.metadata_json["recipe_id"])

    return JobStatusResponse(
        id=job.id,
        status=job.status,
        platform=job.platform,
        source_url=job.source_url,
        error=error,
        metadata=metadata,
        recipe_id=recipe_id,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobStatusResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def submit_video_url(
    request: VideoURLRequest,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> JobStatusResponse:
    """Submit a video URL for processing."""
    url = str(request.url)

    # Quick platform detection (regex only, no network)
    platform = detect_platform(url)
    if platform is None:
        # Check if it could be a short link from a supported platform
        if not any(host in url for host in ["tiktok.com", "instagram.com"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "UNSUPPORTED_PLATFORM",
                        "message": "URL must be from TikTok or Instagram.",
                    }
                },
            )
        platform = "unknown"

    # Check cache: existing completed job with same URL
    result = await db.execute(
        select(ProcessingJob).where(
            ProcessingJob.source_url == url,
            ProcessingJob.status == "complete",
        )
    )
    existing_job = result.scalar_one_or_none()
    if existing_job:
        return _job_to_response(existing_job)

    # Create new job
    job = ProcessingJob(
        id=uuid.uuid4(),
        source_url=url,
        normalized_url=url,  # Will be updated by the worker
        platform=platform,
        status="pending",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch Celery task
    process_video.delay(str(job.id))

    return _job_to_response(job)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> JobStatusResponse:
    """Get the status and metadata of a processing job."""
    job = await db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Job {job_id} not found.",
                }
            },
        )
    return _job_to_response(job)
