"""Async SQLite persistence: users, settings, stats, bans and a file cache."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite

# Default per-user settings.
DEFAULT_SETTINGS: dict[str, Any] = {
    "video_quality": "best",   # best | 1080 | 720 | 480 | 360
    "audio_quality": "192",    # 128 | 192 | 320  (kbps)
    "default_action": "ask",   # ask | audio | video
}

VIDEO_QUALITY_CHOICES = ["best", "1080", "720", "480", "360"]
AUDIO_QUALITY_CHOICES = ["128", "192", "320"]
DEFAULT_ACTION_CHOICES = ["ask", "audio", "video"]


@dataclass
class UserRow:
    id: int
    username: str | None
    first_name: str | None
    joined_at: int
    is_banned: int
    downloads_count: int
    settings: dict[str, Any]


def cache_key(url: str, kind: str, quality: str) -> str:
    raw = f"{url}|{kind}|{quality}".encode("utf-8", "ignore")
    return hashlib.sha1(raw).hexdigest()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._create_tables()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "Database not connected"
        return self._db

    async def _create_tables(self) -> None:
        await self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY,
                username        TEXT,
                first_name      TEXT,
                joined_at       INTEGER NOT NULL,
                is_banned       INTEGER NOT NULL DEFAULT 0,
                downloads_count INTEGER NOT NULL DEFAULT 0,
                settings        TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS downloads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                url        TEXT,
                kind       TEXT,
                quality    TEXT,
                title      TEXT,
                size       INTEGER,
                created_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_downloads_user
                ON downloads(user_id, created_at);

            CREATE TABLE IF NOT EXISTS cache (
                key        TEXT PRIMARY KEY,
                file_id    TEXT NOT NULL,
                file_type  TEXT NOT NULL,
                title      TEXT,
                duration   INTEGER,
                created_at INTEGER NOT NULL
            );
            """
        )
        await self.db.commit()

    # ------------------------------------------------------------------ #
    #  Users
    # ------------------------------------------------------------------ #
    async def upsert_user(
        self, user_id: int, username: str | None, first_name: str | None
    ) -> UserRow:
        now = int(time.time())
        await self.db.execute(
            """
            INSERT INTO users (id, username, first_name, joined_at, settings)
            VALUES (?, ?, ?, ?, '{}')
            ON CONFLICT(id) DO UPDATE SET
                username   = excluded.username,
                first_name = excluded.first_name
            """,
            (user_id, username, first_name, now),
        )
        await self.db.commit()
        row = await self.get_user(user_id)
        assert row is not None
        return row

    async def get_user(self, user_id: int) -> UserRow | None:
        async with self.db.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return self._row_to_user(row)

    def _row_to_user(self, row: aiosqlite.Row) -> UserRow:
        try:
            settings = json.loads(row["settings"] or "{}")
        except (json.JSONDecodeError, TypeError):
            settings = {}
        merged = {**DEFAULT_SETTINGS, **settings}
        return UserRow(
            id=row["id"],
            username=row["username"],
            first_name=row["first_name"],
            joined_at=row["joined_at"],
            is_banned=row["is_banned"],
            downloads_count=row["downloads_count"],
            settings=merged,
        )

    async def get_settings(self, user_id: int) -> dict[str, Any]:
        user = await self.get_user(user_id)
        return user.settings if user else dict(DEFAULT_SETTINGS)

    async def set_setting(self, user_id: int, key: str, value: Any) -> None:
        settings = await self.get_settings(user_id)
        settings[key] = value
        await self.db.execute(
            "UPDATE users SET settings = ? WHERE id = ?",
            (json.dumps(settings), user_id),
        )
        await self.db.commit()

    async def set_banned(self, user_id: int, banned: bool) -> None:
        await self.db.execute(
            "UPDATE users SET is_banned = ? WHERE id = ?",
            (1 if banned else 0, user_id),
        )
        await self.db.commit()

    async def is_banned(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return bool(user and user.is_banned)

    # ------------------------------------------------------------------ #
    #  Downloads / stats / quota
    # ------------------------------------------------------------------ #
    async def record_download(
        self,
        user_id: int,
        url: str,
        kind: str,
        quality: str,
        title: str,
        size: int,
    ) -> None:
        now = int(time.time())
        await self.db.execute(
            """INSERT INTO downloads (user_id, url, kind, quality, title, size, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, url, kind, quality, title, size, now),
        )
        await self.db.execute(
            "UPDATE users SET downloads_count = downloads_count + 1 WHERE id = ?",
            (user_id,),
        )
        await self.db.commit()

    async def downloads_last_24h(self, user_id: int) -> int:
        cutoff = int(time.time()) - 86400
        async with self.db.execute(
            "SELECT COUNT(*) AS c FROM downloads WHERE user_id = ? AND created_at >= ?",
            (user_id, cutoff),
        ) as cur:
            row = await cur.fetchone()
        return int(row["c"]) if row else 0

    async def global_stats(self) -> dict[str, int]:
        out: dict[str, int] = {}
        async with self.db.execute("SELECT COUNT(*) AS c FROM users") as cur:
            out["users"] = int((await cur.fetchone())["c"])
        async with self.db.execute(
            "SELECT COUNT(*) AS c FROM users WHERE is_banned = 1"
        ) as cur:
            out["banned"] = int((await cur.fetchone())["c"])
        async with self.db.execute("SELECT COUNT(*) AS c FROM downloads") as cur:
            out["downloads"] = int((await cur.fetchone())["c"])
        cutoff = int(time.time()) - 86400
        async with self.db.execute(
            "SELECT COUNT(*) AS c FROM downloads WHERE created_at >= ?", (cutoff,)
        ) as cur:
            out["downloads_24h"] = int((await cur.fetchone())["c"])
        async with self.db.execute(
            "SELECT COUNT(DISTINCT user_id) AS c FROM downloads WHERE created_at >= ?",
            (cutoff,),
        ) as cur:
            out["active_24h"] = int((await cur.fetchone())["c"])
        return out

    async def all_user_ids(self) -> list[int]:
        async with self.db.execute(
            "SELECT id FROM users WHERE is_banned = 0"
        ) as cur:
            rows = await cur.fetchall()
        return [int(r["id"]) for r in rows]

    async def user_stats(self, user_id: int) -> dict[str, int]:
        user = await self.get_user(user_id)
        return {
            "total": user.downloads_count if user else 0,
            "today": await self.downloads_last_24h(user_id),
        }

    # ------------------------------------------------------------------ #
    #  Cache (url+kind+quality -> Telegram file_id)
    # ------------------------------------------------------------------ #
    async def cache_get(self, key: str) -> dict[str, Any] | None:
        async with self.db.execute(
            "SELECT * FROM cache WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {
            "file_id": row["file_id"],
            "file_type": row["file_type"],
            "title": row["title"],
            "duration": row["duration"],
        }

    async def cache_put(
        self,
        key: str,
        file_id: str,
        file_type: str,
        title: str,
        duration: int | None,
    ) -> None:
        now = int(time.time())
        await self.db.execute(
            """INSERT INTO cache (key, file_id, file_type, title, duration, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET file_id = excluded.file_id""",
            (key, file_id, file_type, title, duration, now),
        )
        await self.db.commit()

    async def cache_invalidate(self, key: str) -> None:
        await self.db.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self.db.commit()
