from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class VideoSource(str, Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"


class VideoItem(BaseModel):
    id: str
    source: VideoSource
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    author_name: str = ""
    author_handle: str = ""
    author_profile_url: Optional[str] = None
    channel_url: Optional[str] = None
    original_post_url: Optional[str] = None
    published_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    embed_url: Optional[str] = None
    can_embed: bool = False


class SearchRequest(BaseModel):
    query: str
    limit: int = 30
    offset: int = 0
    sources: list[VideoSource] | None = None


class FeedRequest(BaseModel):
    limit: int = 30
    offset: int = 0
