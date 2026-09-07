from __future__ import annotations
import json
import time
from typing import Optional

import aiosqlite


class Cache:
    """Simple SQLite-backed cache for search/trending results.

    Avoids hammering external scrapers/APIs on repeat searches.
    Keys are namespaced per source + operation type so different
    platforms don't collide.
    """

    def __init__(self, db_path: str = "shorts.db", ttl_seconds: int = 10800):
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._db: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        await self._db.commit()

    @staticmethod
    def make_key(source: str, op: str, query: str = "") -> str:
        return f"{source}:{op}:{query.strip().lower()}"

    async def get(self, key: str) -> Optional[list]:
        if not self._db:
            return None
        cursor = await self._db.execute(
            "SELECT data, created_at FROM cache WHERE cache_key = ?", (key,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        data_raw, created_at = row
        if time.time() - created_at > self.ttl_seconds:
            await self.delete(key)
            return None
        try:
            return json.loads(data_raw)
        except Exception:
            return None

    async def set(self, key: str, data: list) -> None:
        if not self._db:
            return
        await self._db.execute(
            "INSERT OR REPLACE INTO cache (cache_key, data, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(data, default=str), time.time()),
        )
        await self._db.commit()

    async def delete(self, key: str) -> None:
        if not self._db:
            return
        await self._db.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
        await self._db.commit()

    async def all_values(self, limit: int = 200) -> list[list]:
        """Return most recent cached lists, for building the auto feed."""
        if not self._db:
            return []
        cursor = await self._db.execute(
            "SELECT data FROM cache ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        await cursor.close()
        result = []
        for (data_raw,) in rows:
            try:
                result.append(json.loads(data_raw))
            except Exception:
                continue
        return result

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None
