from __future__ import annotations
import asyncio
import itertools
import logging
from typing import Optional

from .cache import Cache
from .models import VideoItem, VideoSource
from .sources import BaseSource

log = logging.getLogger(__name__)


class Aggregator:
    """Merges results from multiple sources, dedupes, and interleaves."""

    def __init__(self, sources: list[BaseSource], cache: Cache):
        self.sources = sources
        self.cache = cache

    def available_sources(self) -> list[BaseSource]:
        return [s for s in self.sources if s.is_available]

    @staticmethod
    def _dedupe(items: list[VideoItem]) -> list[VideoItem]:
        seen = set()
        unique = []
        for item in items:
            if item.id in seen:
                continue
            seen.add(item.id)
            unique.append(item)
        return unique

    @staticmethod
    def _interleave(groups: list[list[VideoItem]]) -> list[VideoItem]:
        """Round-robin interleave so sources are mixed, not stacked."""
        merged: list[VideoItem] = []
        groups = [g for g in groups if g]
        if not groups:
            return merged
        for i in itertools.count():
            progressed = False
            for group in groups:
                if i < len(group):
                    merged.append(group[i])
                    progressed = True
            if not progressed:
                break
        return merged

    @staticmethod
    def _alternate_sort_multicriteria(item: VideoItem) -> tuple:
        """For feed ordering we rely on interleave order; keep simple."""
        return 0

    async def search(self, query: str, limit: int = 30, offset: int = 0) -> list[VideoItem]:
        sources = self.available_sources()
        if not sources:
            return []

        per_source_limit = max(limit // len(sources), 8)

        async def run_source(src: BaseSource) -> list[VideoItem]:
            cache_key = self.cache.make_key(src.name, "search", query)
            cached = await self.cache.get(cache_key)
            if cached:
                # Convert cached dicts back to VideoItem
                return [VideoItem(**c) for c in cached]
            try:
                results = await src.search(query, per_source_limit)
            except Exception:
                log.exception("Source %s failed during search", src.name)
                results = []
            # Store cache
            await self.cache.set(cache_key, [r.dict() for r in results])
            return results

        groups = await asyncio.gather(*(run_source(s) for s in sources))
        merged = self._dedupe(self._interleave(groups))
        return merged[offset:offset + limit]

    async def feed(self, limit: int = 30, offset: int = 0) -> list[VideoItem]:
        """Build an auto feed from cached recent/trending results.

        Round-robin so all platforms contribute even if a source is blocked.
        """
        sources = self.available_sources()
        if not sources:
            return []

        per_source = max(limit // len(sources), 8)

        async def run_trending(src: BaseSource) -> list[VideoItem]:
            cache_key = self.cache.make_key(src.name, "trending")
            cached = await self.cache.get(cache_key)
            if cached:
                return [VideoItem(**c) for c in cached]
            try:
                results = await src.get_trending(per_source)
            except Exception:
                log.exception("Source %s trending failed", src.name)
                results = []
            await self.cache.set(cache_key, [r.dict() for r in results])
            return results

        # If we have cached searches, use them for a richer feed rather than
        # hitting trending every time (avoids quota hammering).
        cached_lists = await self.cache.all_values(limit=100)
        if cached_lists:
            from_cached: list[VideoItem] = []
            for lst in cached_lists:
                for item in lst:
                    from_cached.append(VideoItem(**item))
            if from_cached:
                from_cached = self._dedupe(self._interleave(
                    [[i for i in from_cached if i.source == vs] for vs in VideoSource]
                ))
                return from_cached[offset:offset + limit]

        groups = await asyncio.gather(*(run_trending(s) for s in sources))
        merged = self._dedupe(self._interleave(groups))
        if not merged:
            # Last-resort fallback so a fresh install (no API keys yet, or
            # all scrapers blocked) still shows a working feed instead of
            # an empty screen. Demo content is static + safe.
            demo = next((s for s in self.sources if s.name == "demo"), None)
            if demo is not None:
                try:
                    merged = await demo.get_trending(limit)
                except Exception:
                    log.exception("Demo fallback failed")
                    merged = []
        return merged[offset:offset + limit]
