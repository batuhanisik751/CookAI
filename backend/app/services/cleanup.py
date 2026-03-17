import logging
import shutil
import time
from pathlib import Path

from sqlalchemy import update

from app.core.config import settings
from app.core.database import get_sync_session
from app.models.job import ProcessingJob

logger = logging.getLogger(__name__)


def cleanup_job_media(job_id: str, media_dir: str) -> bool:
    """
    Delete a specific job's media directory.

    Returns True if cleanup succeeded or directory didn't exist.
    """
    path = Path(media_dir)
    if not path.exists():
        return True

    # Safety check: ensure path is within temp media dir
    resolved = path.resolve()
    allowed = Path(settings.temp_media_dir).resolve()
    if not str(resolved).startswith(str(allowed)):
        logger.error(
            "Refusing to delete path outside media dir: %s (job %s)",
            media_dir,
            job_id,
        )
        return False

    try:
        shutil.rmtree(path)
        logger.info("Cleaned up media for job %s: %s", job_id, media_dir)
        return True
    except OSError as e:
        logger.error("Failed to cleanup media for job %s: %s", job_id, e)
        return False


def cleanup_expired_media(max_age_hours: int | None = None) -> int:
    """
    Remove media directories older than the configured TTL.

    Scans the temp media directory for job directories and removes those
    older than max_age_hours. Also updates the corresponding DB records.

    Returns the number of directories removed.
    """
    max_age = max_age_hours or settings.media_ttl_hours
    media_root = Path(settings.temp_media_dir)

    if not media_root.exists():
        return 0

    cutoff_time = time.time() - (max_age * 3600)
    removed_count = 0

    for job_dir in media_root.iterdir():
        if not job_dir.is_dir():
            continue

        try:
            dir_mtime = job_dir.stat().st_mtime
            if dir_mtime < cutoff_time:
                shutil.rmtree(job_dir)
                removed_count += 1
                logger.info("Cleaned up expired media: %s", job_dir.name)

                # Clear media_dir in DB
                with get_sync_session() as session:
                    session.execute(
                        update(ProcessingJob)
                        .where(ProcessingJob.media_dir == str(job_dir))
                        .values(media_dir=None)
                    )
        except OSError as e:
            logger.error("Failed to cleanup %s: %s", job_dir, e)

    logger.info("Expired media cleanup: removed %d directories", removed_count)
    return removed_count
