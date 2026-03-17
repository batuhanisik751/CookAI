import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl

from app.schemas.error import ErrorDetail


class VideoURLRequest(BaseModel):
    url: HttpUrl


class VideoMetadata(BaseModel):
    duration_seconds: float | None = None
    creator_handle: str | None = None
    caption: str | None = None
    title: str | None = None
    description: str | None = None
    hashtags: list[str] | None = None
    thumbnail_url: str | None = None


class JobStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    platform: str
    source_url: str
    error: ErrorDetail | None = None
    metadata: VideoMetadata | None = None
    recipe_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
