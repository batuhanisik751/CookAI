import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.deps import get_db
from app.main import app
from app.models.base import Base

# --- Async DB fixtures (for API tests) ---


@pytest.fixture
async def async_db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_db_session(async_db_engine):
    async_session = async_sessionmaker(
        bind=async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def client(async_db_session):
    async def override_get_db():
        yield async_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Sync DB fixtures (for service/worker tests) ---


@pytest.fixture
def sync_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sync_db_session(sync_db_engine):
    session_factory = sessionmaker(bind=sync_db_engine)
    session = session_factory()
    yield session
    session.close()


# --- Sample data fixtures ---


@pytest.fixture
def sample_tiktok_url():
    return "https://www.tiktok.com/@cookingwithme/video/7312345678901234567"


@pytest.fixture
def sample_instagram_url():
    return "https://www.instagram.com/reel/ABC123def456/"


@pytest.fixture
def sample_job_id():
    return str(uuid.uuid4())


@pytest.fixture
def tmp_media_dir(tmp_path):
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    return str(media_dir)


# --- Mock fixtures ---


@pytest.fixture
def mock_ytdlp():
    with patch("app.services.video_downloader.yt_dlp.YoutubeDL") as mock:
        instance = MagicMock()
        mock.return_value.__enter__ = MagicMock(return_value=instance)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        instance.extract_info.return_value = {
            "duration": 30,
            "width": 1080,
            "height": 1920,
            "uploader": "cookingwithme",
            "description": "Easy pasta recipe!",
            "thumbnail": "https://example.com/thumb.jpg",
        }
        yield instance


@pytest.fixture
def mock_ffmpeg():
    with patch("app.services.media_extractor.asyncio.create_subprocess_exec") as mock:
        process = AsyncMock()
        process.communicate.return_value = (b"{}", b"")
        process.returncode = 0
        mock.return_value = process
        yield mock


@pytest.fixture
def mock_httpx():
    with patch("app.services.url_validator.httpx.AsyncClient") as mock:
        client_instance = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client_instance)
        mock.return_value.__aexit__ = AsyncMock(return_value=False)
        response = MagicMock()
        response.url = "https://www.tiktok.com/@cookingwithme/video/7312345678901234567"
        response.status_code = 200
        client_instance.head.return_value = response
        yield client_instance
