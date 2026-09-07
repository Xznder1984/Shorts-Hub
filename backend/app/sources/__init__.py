from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from ..models import VideoItem


class BaseSource(ABC):
    """Base class for all video source modules.
    
    Each source (YouTube, TikTok, Instagram) implements this interface.
    Sources are isolated so one breaking doesn't take down the whole app.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this source is properly configured and ready to use."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 30) -> list[VideoItem]:
        """Search for videos matching the query."""
        ...

    @abstractmethod
    async def get_trending(self, limit: int = 30) -> list[VideoItem]:
        """Get trending/popular videos from this source."""
        ...
