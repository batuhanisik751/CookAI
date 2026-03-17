import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.job import ProcessingJob

TIKTOK_URL = "https://www.tiktok.com/@user/video/1234567890123456789"
TIKTOK_SHORT = "https://www.tiktok.com/@user/video/123"
INSTAGRAM_URL = "https://www.instagram.com/reel/ABC123def456/"


class TestSubmitVideoUrl:
    @pytest.mark.asyncio
    @patch("app.api.jobs.process_video")
    async def test_submit_valid_tiktok_url(
        self,
        mock_task,
        client,
        async_db_session,
    ):
        mock_task.delay.return_value = MagicMock(
            id="celery-task-id",
        )

        response = await client.post(
            "/api/jobs",
            json={"url": TIKTOK_URL},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["platform"] == "tiktok"
        assert "id" in data
        mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.api.jobs.process_video")
    async def test_submit_valid_instagram_url(
        self,
        mock_task,
        client,
        async_db_session,
    ):
        mock_task.delay.return_value = MagicMock(
            id="celery-task-id",
        )

        response = await client.post(
            "/api/jobs",
            json={"url": INSTAGRAM_URL},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"
        assert data["platform"] == "instagram"

    @pytest.mark.asyncio
    async def test_submit_unsupported_url(self, client):
        response = await client.post(
            "/api/jobs",
            json={"url": "https://www.youtube.com/watch?v=abc"},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"]["code"] == "UNSUPPORTED_PLATFORM"

    @pytest.mark.asyncio
    async def test_submit_invalid_url_format(self, client):
        response = await client.post(
            "/api/jobs",
            json={"url": "not-a-url"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_missing_url(self, client):
        response = await client.post("/api/jobs", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch("app.api.jobs.process_video")
    async def test_cache_hit_returns_existing(
        self,
        mock_task,
        client,
        async_db_session,
    ):
        job = ProcessingJob(
            id=uuid.uuid4(),
            source_url=TIKTOK_URL,
            normalized_url=TIKTOK_URL,
            platform="tiktok",
            status="complete",
            metadata_json={"duration_seconds": 30},
        )
        async_db_session.add(job)
        await async_db_session.commit()

        response = await client.post(
            "/api/jobs",
            json={"url": TIKTOK_URL},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "complete"
        assert data["id"] == str(job.id)
        mock_task.delay.assert_not_called()


class TestGetJobStatus:
    @pytest.mark.asyncio
    async def test_get_existing_job(
        self,
        client,
        async_db_session,
    ):
        job = ProcessingJob(
            id=uuid.uuid4(),
            source_url=TIKTOK_SHORT,
            normalized_url=TIKTOK_SHORT,
            platform="tiktok",
            status="downloading",
        )
        async_db_session.add(job)
        await async_db_session.commit()

        response = await client.get(f"/api/jobs/{job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "downloading"
        assert data["platform"] == "tiktok"

    @pytest.mark.asyncio
    async def test_get_nonexistent_job(self, client):
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/jobs/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"]["code"] == "JOB_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_job_with_error(
        self,
        client,
        async_db_session,
    ):
        job = ProcessingJob(
            id=uuid.uuid4(),
            source_url=TIKTOK_SHORT,
            normalized_url=TIKTOK_SHORT,
            platform="tiktok",
            status="failed",
            error_code="DOWNLOAD_FAILED",
            error_message="Network error",
        )
        async_db_session.add(job)
        await async_db_session.commit()

        response = await client.get(f"/api/jobs/{job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"]["code"] == "DOWNLOAD_FAILED"

    @pytest.mark.asyncio
    async def test_get_job_with_metadata(
        self,
        client,
        async_db_session,
    ):
        job = ProcessingJob(
            id=uuid.uuid4(),
            source_url=TIKTOK_SHORT,
            normalized_url=TIKTOK_SHORT,
            platform="tiktok",
            status="complete",
            metadata_json={
                "duration_seconds": 30.5,
                "resolution": "1080x1920",
                "creator_handle": "chef_user",
                "caption": "Easy pasta recipe",
            },
        )
        async_db_session.add(job)
        await async_db_session.commit()

        response = await client.get(f"/api/jobs/{job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["duration_seconds"] == 30.5
        assert data["metadata"]["creator_handle"] == "chef_user"

    @pytest.mark.asyncio
    async def test_invalid_job_id_format(self, client):
        response = await client.get("/api/jobs/not-a-uuid")
        assert response.status_code == 422
