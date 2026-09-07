from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import VideoItem, VideoSource
from app.aggregator import Aggregator
from app.sources.demo import DemoSource
from app.sources.youtube import YouTubeSource


def test_parse_iso_duration_seconds():
    assert YouTubeSource._parse_iso_duration("PT15S") == 15.0
    assert YouTubeSource._parse_iso_duration("PT1M2S") == 62.0
    assert YouTubeSource._parse_iso_duration("PT1H5M") == 3900.0
    assert YouTubeSource._parse_iso_duration("P1DT2H3M4S") == 93784.0
    assert YouTubeSource._parse_iso_duration("") is None
    assert YouTubeSource._parse_iso_duration("garbage") is None


def test_is_short_duration():
    assert YouTubeSource._is_short_duration("PT15S") is True
    assert YouTubeSource._is_short_duration("PT59S") is True
    assert YouTubeSource._is_short_duration("PT1M0S") is True   # exactly 60s = short
    assert YouTubeSource._is_short_duration("PT1M1S") is False
    assert YouTubeSource._is_short_duration("PT10M") is False
    assert YouTubeSource._is_short_duration("") is False


def test_parse_hashtags():
    tags = YouTubeSource._parse_hashtags("Hello #world #funny, #shorts.")
    assert "world" in tags
    assert "funny" in tags
    assert "shorts" in tags
    assert len(tags) == 3
    # Duplicates removed
    tags = YouTubeSource._parse_hashtags("#a #a #b")
    assert tags == ["a", "b"]


def test_aggregator_interleave():
    # Two sources with staggered results should round-robin mix
    group_a = [VideoItem(id=f"a{i}", source=VideoSource.YOUTUBE, caption="") for i in range(5)]
    group_b = [VideoItem(id=f"b{i}", source=VideoSource.TIKTOK, caption="") for i in range(5)]
    merged = Aggregator._interleave([group_a, group_b])
    assert len(merged) == 10
    sources = [v.source for v in merged]
    # Should alternate y/t/y/t...
    assert sources[0] == VideoSource.YOUTUBE
    assert sources[1] == VideoSource.TIKTOK
    assert sources[2] == VideoSource.YOUTUBE


def test_aggregator_dedupe():
    items = [
        VideoItem(id="x", source=VideoSource.YOUTUBE, caption=""),
        VideoItem(id="x", source=VideoSource.YOUTUBE, caption=""),
        VideoItem(id="y", source=VideoSource.TIKTOK, caption=""),
    ]
    assert len(Aggregator._dedupe(items)) == 2


def test_aggregator_empty_interleave():
    assert Aggregator._interleave([[], []]) == []
    only = [VideoItem(id="a", source=VideoSource.YOUTUBE, caption="")]
    assert Aggregator._interleave([[only]]) == [only]


def test_demo_source_search_and_trending():
    import asyncio
    demo = DemoSource(enabled=True)
    assert demo.is_available is True
    all_items = asyncio.run(demo.get_trending(10))
    assert len(all_items) == 4
    matches = asyncio.run(demo.search("funny", 10))
    assert len(matches) >= 1
    assert all("funny" in (i.caption + " " + " ".join(i.hashtags)).lower() for i in matches)
    no_match = asyncio.run(demo.search("zzzznothing", 10))
    assert no_match == []


def test_configured_sources_use_demo_fallback(tmp_path):
    """When all real sources return nothing, aggregator.search should
    still return demo content (graceful fallback) instead of empty."""
    import asyncio
    from app.sources import BaseSource
    from app.cache import Cache

    class AlwaysDownSource(BaseSource):
        name = "broken"
        @property
        def is_available(self) -> bool:
            return True
        async def search(self, query, limit=30):
            return []
        async def get_trending(self, limit=30):
            return []

    demo = DemoSource(enabled=True)
    cache = Cache(str(tmp_path / "t.db"), ttl_seconds=60)
    asyncio.run(cache.init())
    agg = Aggregator([AlwaysDownSource(), demo], cache)
    result = asyncio.run(agg.search("shorts", limit=10))
    assert len(result) >= 1
    assert all(i.source in (VideoSource.YOUTUBE, VideoSource.TIKTOK, VideoSource.INSTAGRAM) for i in result)
    assert "shorts" in (result[0].caption + " " + " ".join(result[0].hashtags)).lower()
    asyncio.run(cache.close())
