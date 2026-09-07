from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .aggregator import Aggregator
from .cache import Cache
from .models import VideoItem, VideoSource
from .sources.demo import DemoSource
from .sources.instagram import InstagramSource
from .sources.tiktok import TikTokSource
from .sources.youtube import YouTubeSource

load_dotenv()

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DB_PATH = os.getenv("SHORTS_DB", "shorts.db")
CACHE_TTL = int(os.getenv("CACHE_TTL", "10800"))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

cache = Cache(DB_PATH, CACHE_TTL)
youtube = YouTubeSource(
    api_key=os.getenv("YOUTUBE_API_KEY", ""),
    rate_limit_per_minute=RATE_LIMIT,
)
tiktok = TikTokSource(
    session_cookie=os.getenv("TIKTOK_SESSION_COOKIE", ""),
    rate_limit_per_minute=RATE_LIMIT,
)
instagram = InstagramSource(
    username=os.getenv("INSTAGRAM_USERNAME", ""),
    password=os.getenv("INSTAGRAM_PASSWORD", ""),
    rate_limit_per_minute=RATE_LIMIT,
)
demo = DemoSource(enabled=os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes", "on"))
aggregator = Aggregator([youtube, tiktok, instagram, demo], cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.init()
    log.info("Shorts Hub backend started")
    log.info("Available sources: %s", [s.name for s in aggregator.available_sources()])
    yield
    await cache.close()
    await asyncio_gather_close()


import asyncio


async def asyncio_gather_close():
    for s in aggregator.sources:
        if hasattr(s, "close"):
            try:
                await s.close()
            except Exception:
                pass


app = FastAPI(
    title="Shorts Hub API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StatusOut(BaseModel):
    available_sources: list[str]
    disabled_sources: list[str]
    version: str


@app.get("/api/status", response_model=StatusOut)
async def get_status():
    all_names = [s.name for s in aggregator.sources]
    available = [s.name for s in aggregator.available_sources()]
    return StatusOut(
        available_sources=available,
        disabled_sources=[n for n in all_names if n not in available],
        version=app.version,
    )


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sources: Optional[str] = Query(None, description="Comma-separated source filter"),
):
    if not q.strip():
        raise HTTPException(400, "Query is required")
    results = await aggregator.search(q.strip(), limit=limit, offset=offset)
    return {"query": q.strip(), "count": len(results), "results": [r.model_dump() for r in results]}


@app.get("/api/feed")
async def feed(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    results = await aggregator.feed(limit=limit, offset=offset)
    return {"count": len(results), "results": [r.model_dump() for r in results]}


@app.get("/api/health")
async def health():
    return {"status": "ok", "sources": [s.name for s in aggregator.available_sources()]}
