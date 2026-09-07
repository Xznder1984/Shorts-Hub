from __future__ import annotations
import asyncio
import logging
from typing import Optional
from urllib.parse import quote

import httpx

from ..models import VideoItem, VideoSource
from . import BaseSource

log = logging.getLogger(__name__)

TIKTOK_SEARCH_URL = "https://www.tiktok.com/api/search/general/full/"
TIKTOK_TRENDING_URL = "https://www.tiktok.com/api/item/list/"


class TikTokSource(BaseSource):
    """TikTok source using a lightweight HTTP scraper.

    FRAGILE MODULE: TikTok has no official public API for this use case.
    This module is isolated so it can be disabled or swapped without affecting
    the rest of the app. If TikTok changes their endpoints and this breaks,
    the app still works with YouTube-only content.

    This implementation uses TikTok's public web-facing internal API which
    requires no login. It may need periodic updates. It is best-effort.
    """

    name = "tiktok"

    def __init__(
        self,
        session_cookie: str = "",
        rate_limit_per_minute: int = 20,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.session_cookie = session_cookie or ""
        self.rate_limit_per_minute = rate_limit_per_minute
        self._http = http_client or httpx.AsyncClient(timeout=15)
        self._request_lock = asyncio.Lock()
        self._last_request_time = 0.0

    @property
    def is_available(self) -> bool:
        return True

    async def _rate_limit(self) -> None:
        async with self._request_lock:
            interval = 60.0 / max(self.rate_limit_per_minute, 1)
            now = asyncio.get_event_loop().time()
            wait = self._last_request_time + interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_time = asyncio.get_event_loop().time()

    def _headers(self) -> dict:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.tiktok.com/",
        }
        if self.session_cookie:
            headers["Cookie"] = f"sessionid={self.session_cookie}"
        return headers

    @staticmethod
    def _parse_hashtags(caption: str) -> list[str]:
        hashtags = []
        for word in caption.split():
            if word.startswith("#") and len(word) > 1:
                tag = word.lstrip("#").rstrip(",.")
                if tag and tag not in hashtags:
                    hashtags.append(tag)
        return hashtags

    @staticmethod
    def _item_to_video(item: dict) -> Optional[VideoItem]:
        try:
            item_id = item.get("id") or item.get("aweme_id")
            if not item_id:
                return None
            author = item.get("author", {}) or {}
            caption = item.get("desc", "") or ""
            durations = item.get("video", {}).get("duration") or item.get("duration")
            duration_sec = float(durations / 1000) if isinstance(durations, (int, float)) and durations > 1000 else (float(durations) if durations else None)

            return VideoItem(
                id=f"tt_{item_id}",
                source=VideoSource.TIKTOK,
                video_url=item.get("video", {}).get("play_addr", {}).get("url_list", [None])[0]
                          or item.get("video", {}).get("url_list", [None])[0],
                thumbnail_url=item.get("video", {}).get("cover", {}).get("url_list", [None])[0]
                              or item.get("video", {}).get("origin_cover", {}).get("url_list", [None])[0],
                caption=caption,
                hashtags=TikTokSource._parse_hashtags(caption),
                author_name=author.get("nickname", ""),
                author_handle=author.get("unique_id", "") or author.get("sec_uid", ""),
                author_profile_url=f"https://www.tiktok.com/@{author.get('unique_id', '')}" if author.get("unique_id") else None,
                channel_url=f"https://www.tiktok.com/@{author.get('unique_id', '')}" if author.get("unique_id") else None,
                original_post_url=f"https://www.tiktok.com/@{author.get('unique_id', '')}/video/{item_id}" if author.get("unique_id") else None,
                published_at=None,
                duration_seconds=duration_sec,
                can_embed=False,
            )
        except Exception:
            log.exception("Failed to parse TikTok item")
            return None

    async def search(self, query: str, limit: int = 30) -> list[VideoItem]:
        params = {
            "keyword": query,
            "count": limit,
            "device_platform": "webapp",
            "aid": "1988",
            "channel": "channel_pc_web",
            "search_id": "",
        }
        try:
            await self._rate_limit()
            async with self._http.get(TIKTOK_SEARCH_URL, params=params, headers=self._headers()) as resp:
                if resp.status_code != 200:
                    log.warning("TikTok search returned status %s", resp.status_code)
                    return []
                data = resp.json()
        except Exception:
            log.exception("TikTok search failed")
            return []

        items = []
        for section in data.get("data", []):
            for item in section.get("card_item", []) or []:
                video = TikTokSource._item_to_video(item)
                if video:
                    items.append(video)
                    if len(items) >= limit:
                        break
            if len(items) >= limit:
                break
        return items

    async def get_trending(self, limit: int = 30) -> list[VideoItem]:
        params = {
            "count": limit,
            "device_platform": "webapp",
            "aid": "1988",
        }
        try:
            await self._rate_limit()
            async with self._http.get(TIKTOK_TRENDING_URL, params=params, headers=self._headers()) as resp:
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception:
            log.exception("TikTok trending failed")
            return []

        items = [TikTokSource._item_to_video(i) for i in data.get("itemList", [])]
        return [i for i in items if i]

    async def close(self) -> None:
        await self._http.aclose()
