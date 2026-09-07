from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models import VideoItem, VideoSource
from . import BaseSource

log = logging.getLogger(__name__)

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeSource(BaseSource):
    """Official YouTube Data API v3 source for Shorts.

    Primary, stable integration. Requires a YOUTUBE_API_KEY in .env.
    """

    name = "youtube"

    def __init__(self, api_key: str, rate_limit_per_minute: int = 20, http_client: Optional[httpx.AsyncClient] = None):
        self.api_key = api_key or ""
        self.rate_limit_per_minute = rate_limit_per_minute
        self._http = http_client or httpx.AsyncClient(timeout=15)
        self._request_lock = asyncio.Lock()
        self._last_request_time = 0.0

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def _rate_limit(self) -> None:
        """Simple token-bucket-ish limiter: at least one request per interval."""
        async with self._request_lock:
            interval = 60.0 / max(self.rate_limit_per_minute, 1)
            now = asyncio.get_event_loop().time()
            wait = self._last_request_time + interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = asyncio.get_event_loop().time()

    async def _get(self, endpoint: str, params: dict) -> dict:
        await self._rate_limit()
        params = {**params, "key": self.api_key}
        async with self._http.get(f"{YOUTUBE_API_BASE}/{endpoint}", params=params) as resp:
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _parse_hashtags(description: str) -> list[str]:
        """Extract #hashtags from a YouTube description string."""
        hashtags = []
        for word in description.split():
            if word.startswith("#") and len(word) > 1:
                tag = word.lstrip("#").rstrip(",.")
                if tag and tag not in hashtags:
                    hashtags.append(tag)
        return hashtags

    async def _search_shorts(self, query: str, limit: int) -> list[VideoItem]:
        """Search YouTube and return only Shorts (filter by duration + content).
        
        YouTube Shorts are typically under 60 seconds. We use search.list then
        filter by duration and videoCategory, but the official way to detect
        Shorts reliably is via the videos.list 'contentDetails' + the Shorts URL.
        """
        try:
            data = await self._get("search", {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": min(limit * 3, 50),
                "order": "relevance",
                "safeSearch": "none",
            })
        except Exception:
            log.exception("YouTube search failed for query %r", query)
            return []

        items = data.get("items", [])
        if not items:
            return []

        # Fetch video details in batches to get duration, then filter to shorts.
        video_ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
        details_by_id = await self._fetch_video_details(video_ids)

        results: list[VideoItem] = []
        for item in items:
            vid_id = item["id"].get("videoId")
            if not vid_id:
                continue
            detail = details_by_id.get(vid_id, {})
            snippet = item.get("snippet", {})

            # Only keep short-form videos (<= 60s for Shorts, or contentDetails says shorts)
            duration = detail.get("contentDetails", {}).get("duration", "")
            is_short = self._is_short_duration(duration) or detail.get("contentDetails", {}).get("shorts", False)

            if not is_short:
                continue

            desc = snippet.get("description", "") or ""
            channel_title = snippet.get("channelTitle", "")
            channel_id = snippet.get("channelId", "")

            video = VideoItem(
                id=f"yt_{vid_id}",
                source=VideoSource.YOUTUBE,
                video_url=f"https://www.youtube.com/watch?v={vid_id}",
                thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url")
                           or snippet.get("thumbnails", {}).get("default", {}).get("url"),
                caption=desc[:500] if desc else (snippet.get("title", "") or ""),
                hashtags=self._parse_hashtags(desc),
                author_name=channel_title,
                author_handle=channel_title,
                author_profile_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
                channel_url=f"https://www.youtube.com/channel/{channel_id}" if channel_id else None,
                original_post_url=f"https://www.youtube.com/watch?v={vid_id}",
                published_at=self._to_datetime(snippet.get("publishedAt")),
                duration_seconds=self._parse_iso_duration(duration),
                embed_url=f"https://www.youtube.com/embed/{vid_id}",
                can_embed=True,
            )
            results.append(video)
            if len(results) >= limit:
                break

        return results

    async def _fetch_video_details(self, video_ids: list[str]) -> dict:
        """Fetch video details (duration, etc.) in batches of 50."""
        details: dict = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            try:
                data = await self._get("videos", {
                    "part": "contentDetails",
                    "id": ",".join(batch),
                })
                for item in data.get("items", []):
                    details[item["id"]] = item
            except Exception:
                log.exception("YouTube videos.list failed for batch")
        return details

    async def _get_trending_shorts(self, limit: int) -> list[VideoItem]:
        """Get trending Shorts via the mostPopular videos list filtered to shorts."""
        try:
            data = await self._get("videos", {
                "part": "contentDetails,snippet",
                "chart": "mostPopular",
                "maxResults": min(limit * 3, 50),
                "videoCategoryId": "24",  # Entertainment often carries Shorts
            })
        except Exception:
            log.exception("YouTube trending failed")
            return []

        results: list[VideoItem] = []
        for item in data.get("items", []):
            duration = item.get("contentDetails", {}).get("duration", "")
            if not self._is_short_duration(duration):
                continue
            vid_id = item["id"]
            snippet = item.get("snippet", {})
            desc = snippet.get("description", "") or ""
            video = VideoItem(
                id=f"yt_{vid_id}",
                source=VideoSource.YOUTUBE,
                video_url=f"https://www.youtube.com/watch?v={vid_id}",
                thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                caption=desc[:500] if desc else (snippet.get("title", "") or ""),
                hashtags=self._parse_hashtags(desc),
                author_name=snippet.get("channelTitle", ""),
                author_handle=snippet.get("channelTitle", ""),
                author_profile_url=f"https://www.youtube.com/channel/{snippet.get('channelId', '')}" if snippet.get("channelId") else None,
                channel_url=f"https://www.youtube.com/channel/{snippet.get('channelId', '')}" if snippet.get("channelId") else None,
                original_post_url=f"https://www.youtube.com/watch?v={vid_id}",
                published_at=self._to_datetime(snippet.get("publishedAt")),
                duration_seconds=self._parse_iso_duration(duration),
                embed_url=f"https://www.youtube.com/embed/{vid_id}",
                can_embed=True,
            )
            results.append(video)
            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _is_short_duration(iso_duration: str) -> bool:
        """Determine if an ISO 8601 duration indicates a Short (< 60s)."""
        seconds = YouTubeSource._parse_iso_duration(iso_duration)
        return seconds is not None and seconds <= 60

    @staticmethod
    def _parse_iso_duration(iso_duration: str) -> Optional[float]:
        """Parse ISO 8601 duration like 'PT1M2S' or 'PT15S' to seconds."""
        if not iso_duration:
            return None
        try:
            import re
            match = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", iso_duration)
            if not match:
                return None
            days, hours, minutes, seconds = match.groups()
            total = 0
            if days:
                total += int(days) * 86400
            if hours:
                total += int(hours) * 3600
            if minutes:
                total += int(minutes) * 60
            if seconds:
                total += float(seconds)
            return total
        except Exception:
            return None

    @staticmethod
    def _to_datetime(iso_str: Optional[str]) -> Optional[datetime]:
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except Exception:
            return None

    async def search(self, query: str, limit: int = 30) -> list[VideoItem]:
        return await self._search_shorts(query, limit)

    async def get_trending(self, limit: int = 30) -> list[VideoItem]:
        return await self._get_trending_shorts(limit)

    async def close(self) -> None:
        await self._http.aclose()
