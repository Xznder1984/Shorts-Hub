from __future__ import annotations
import asyncio
import logging
from typing import Optional

import httpx

from ..models import VideoItem, VideoSource
from . import BaseSource

log = logging.getLogger(__name__)

# Instagram public web API endpoints (best-effort, may change)
IG_TAG_MEDIA_URL = "https://www.instagram.com/api/v1/tags/{tag}/web_info"
IG_EXPLORE_URL = "https://www.instagram.com/api/v1/discover/explore"
IG_TOPSEARCH_GRAPHQL = "https://www.instagram.com/api/v1/web/search/topsearch"


class InstagramSource(BaseSource):
    """Instagram Reels source using a lightweight HTTP scraper.

    FRAGILE MODULE: Instagram has no official public API for generic Reels
    search. This module is isolated so it can be disabled or swapped without
    affecting the rest of the app. If Instagram blocks or changes endpoints,
    the app still works with YouTube-only content.

    Using the private Instagram web API, no login is required for basic
    public media. Results are best-effort.
    """

    name = "instagram"

    def __init__(
        self,
        username: str = "",
        password: str = "",
        rate_limit_per_minute: int = 20,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self.username = username or ""
        self.password = password or ""
        self.rate_limit_per_minute = rate_limit_per_minute
        self._http = http_client or httpx.AsyncClient(timeout=15, follow_redirects=True)
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
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.instagram.com/",
            "x-ig-app-id": "936619743392459",
        }

    @staticmethod
    def _parse_hashtags(caption_words: list) -> list[str]:
        hashtags = []
        for node in caption_words or []:
            text = node.get("text", "") or ""
            if text.startswith("#") and len(text) > 1:
                tag = text.lstrip("#").rstrip(",.")
                if tag and tag not in hashtags:
                    hashtags.append(tag)
        return hashtags

    @staticmethod
    def _node_to_video(node: dict) -> Optional[VideoItem]:
        """Convert an Instagram media node to a VideoItem (only reels/videos)."""
        try:
            media_type = node.get("media_type")  # 1=image, 2=video, 8=carousel
            if media_type not in (2, 8):
                return None

            code = node.get("code") or node.get("shortcode")
            if not code:
                return None

            display_resources = node.get("display_resources") or node.get("thumbnail_resources") or []
            thumb = None
            if display_resources:
                thumbs = sorted((r.get("src", "") for r in display_resources if r.get("src")), key=len)
                thumb = thumbs[-1] if thumbs else None
            thumb = thumb or node.get("display_url")

            caption = (node.get("caption") or {}).get("text", "") if isinstance(node.get("caption"), dict) else (node.get("caption") or "")

            video_url = None
            video_versions = node.get("video_versions") or []
            if video_versions:
                videos = sorted(video_versions, key=lambda v: v.get("height", 0), reverse=True)
                video_url = videos[0].get("url")

            owner = node.get("owner") or {}
            username = owner.get("username", "")

            return VideoItem(
                id=f"ig_{code}",
                source=VideoSource.INSTAGRAM,
                video_url=video_url,
                thumbnail_url=thumb or node.get("display_src") or node.get("image_url"),
                caption=caption,
                hashtags=InstagramSource._parse_hashtags((node.get("caption") or {}).get("text_nodes") or node.get("caption_is_edited") or []),
                author_name=owner.get("full_name", "") or username,
                author_handle=username,
                author_profile_url=f"https://www.instagram.com/{username}/" if username else None,
                channel_url=f"https://www.instagram.com/{username}/" if username else None,
                original_post_url=f"https://www.instagram.com/p/{code}/",
                published_at=None,
                duration_seconds=node.get("video_duration") or None,
                can_embed=False,
            )
        except Exception:
            log.exception("Failed to parse Instagram node")
            return None

    async def search(self, query: str, limit: int = 30) -> list[VideoItem]:
        """Search Instagram for reels matching the query (tag-based fallback)."""
        results: list[VideoItem] = []

        # Try tag search first (common pattern for shorts-style content)
        tag = query.strip().lstrip("#").replace(" ", "").lower()
        tag_videos = await self._tag_search(tag, limit)
        results.extend(tag_videos)

        if len(results) >= limit:
            return results[:limit]

        # Fallback: generic keyword search via topsearch
        keyword_videos = await self._keyword_search(query, limit - len(results))
        results.extend(keyword_videos)

        return results[:limit]

    async def _tag_search(self, tag: str, limit: int) -> list[VideoItem]:
        try:
            await self._rate_limit()
            url = IG_TAG_MEDIA_URL.replace("{tag}", tag)
            async with self._http.get(url, headers=self._headers()) as resp:
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception:
            log.exception("Instagram tag search failed for %r", tag)
            return []

        results: list[VideoItem] = []
        media = (data.get("data", {}) or {}).get("recent", {}) or {}
        sections = media.get("sections", []) or []
        for section in sections:
            if section.get("layout_type") == "media_grid":
                for item in section.get("layout_content", {}).get("media", []) or []:
                    video = InstagramSource._node_to_video(item.get("media") or item)
                    if video:
                        results.append(video)
                        if len(results) >= limit:
                            return results
        return results

    async def _keyword_search(self, query: str, limit: int) -> list[VideoItem]:
        try:
            await self._rate_limit()
            params = {"q": query}
            async with self._http.get(IG_TOPSEARCH_GRAPHQL, params=params, headers=self._headers()) as resp:
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception:
            log.exception("Instagram keyword search failed for %r", query)
            return []

        results: list[VideoItem] = []
        try:
            users = data.get("users", []) or []
            for user in users:
                user_obj = user.get("user", {})
                if not user_obj.get("is_private"):
                    pk = user_obj.get("pk")
                    username = user_obj.get("username", "")
                    profile_videos = await self._user_reels(pk, username, limit - len(results))
                    results.extend(profile_videos)
                    if len(results) >= limit:
                        return results
        except Exception:
            log.exception("Instagram keyword parse failed")
        return results

    async def _user_reels(self, pk: str, username: str, limit: int) -> list[VideoItem]:
        try:
            await self._rate_limit()
            url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
            async with self._http.get(url, headers=self._headers()) as resp:
                if resp.status_code != 200:
                    return []
                data = resp.json()
            user_block = (data.get("data", {}) or {}).get("user", {})
            edge = (user_block.get("edge_owner_to_timeline_media", {}) or {}).get("edges", []) or []
            results: list[VideoItem] = []
            for e in edge:
                node = e.get("node", {}) or {}
                video = InstagramSource._node_to_video(node)
                if video:
                    results.append(video)
                    if len(results) >= limit:
                        break
            return results
        except Exception:
            log.exception("Instagram user reels failed for %r", username)
            return []

    async def get_trending(self, limit: int = 30) -> list[VideoItem]:
        # Explore feed is the closest to "trending" for public web API
        try:
            await self._rate_limit()
            async with self._http.get(IG_EXPLORE_URL, headers=self._headers()) as resp:
                if resp.status_code != 200:
                    return []
                data = resp.json()
        except Exception:
            log.exception("Instagram explore failed")
            return []

        results: list[VideoItem] = []
        try:
            sections = (data.get("data", {}) or {}).get("sections", []) or []
            for section in sections:
                for item in (section.get("layout_content", {}) or {}).get("medias", []) or []:
                    media = item.get("media") or item
                    video = InstagramSource._node_to_video(media)
                    if video:
                        results.append(video)
                        if len(results) >= limit:
                            return results
        except Exception:
            log.exception("Instagram explore parse failed")
        return results

    async def close(self) -> None:
        await self._http.aclose()
