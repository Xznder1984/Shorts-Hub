from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from ..models import VideoItem, VideoSource
from . import BaseSource

DEMO_ITEMS: list[tuple[str, str, str, str, list[str]]] = [
    (
        "demo_yt_1",
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "Me at the zoo — the first YouTube video ever. #shorts #history",
        "@jawed",
        ["shorts", "history"],
    ),
    (
        "demo_yt_2",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "Classic vertical short. #shorts #funny",
        "@rickastley",
        ["shorts", "funny"],
    ),
    (
        "demo_tt_1",
        "https://www.tiktok.com/@tiktok",
        "Welcome to TikTok — #fyp #viral",
        "@tiktok",
        ["fyp", "viral"],
    ),
    (
        "demo_ig_1",
        "https://www.instagram.com/reels/",
        "Instagram Reels — #reels #trending",
        "@instagram",
        ["reels", "trending"],
    ),
]


class DemoSource(BaseSource):
    """Placeholder source so a fresh install isn't an empty feed.

    ENABLED ONLY with DEMO_MODE=true in .env (default off).
    Returns static, safe items (real public posts with playable embeds or
    direct links) so you can verify the UI before configuring API keys.
    """

    name = "demo"

    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    @property
    def is_available(self) -> bool:
        return self.enabled

    def _make_item(self, vid_id: str, url: str, caption: str, author: str, tags: list[str]) -> VideoItem:
        is_youtube = vid_id.startswith("demo_yt")
        return VideoItem(
            id=vid_id,
            source=VideoSource.YOUTUBE if is_youtube else (VideoSource.TIKTOK if vid_id.startswith("demo_tt") else VideoSource.INSTAGRAM),
            video_url=url,
            thumbnail_url=f"https://i.ytimg.com/vi/{url.split('v=')[-1]}/hqdefault.jpg" if is_youtube else None,
            caption=caption,
            hashtags=tags,
            author_name=author.lstrip("@"),
            author_handle=author,
            author_profile_url=url,
            channel_url=url,
            original_post_url=url,
            published_at=datetime.now(timezone.utc),
            duration_seconds=30.0,
            embed_url=f"https://www.youtube-nocookie.com/embed/{url.split('v=')[-1]}" if is_youtube else None,
            can_embed=is_youtube,
        )

    async def search(self, query: str, limit: int = 30) -> list[VideoItem]:
        items = [self._make_item(*i) for i in DEMO_ITEMS]
        q = query.strip().lower().lstrip("#")
        if q:
            items = [i for i in items if q in i.caption.lower() or q in " ".join(i.hashtags).lower()]
        return items[:limit]

    async def get_trending(self, limit: int = 30) -> list[VideoItem]:
        return [self._make_item(*i) for i in DEMO_ITEMS][:limit]