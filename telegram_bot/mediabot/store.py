"""A tiny in-memory job store with TTL so callback buttons stay short."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Entry:
    value: Any
    created: float = field(default_factory=time.time)


class JobStore:
    """Maps short tokens to arbitrary payloads (URLs, search results, …).

    Telegram callback_data is limited to 64 bytes, so we never embed long URLs
    in buttons — we stash them here and reference them by token.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._data: dict[str, _Entry] = {}
        self._ttl = ttl_seconds

    def put(self, value: Any) -> str:
        self._evict()
        token = uuid.uuid4().hex[:10]
        self._data[token] = _Entry(value)
        return token

    def get(self, token: str) -> Any | None:
        entry = self._data.get(token)
        if entry is None:
            return None
        if time.time() - entry.created > self._ttl:
            self._data.pop(token, None)
            return None
        return entry.value

    def pop(self, token: str) -> Any | None:
        entry = self._data.pop(token, None)
        return entry.value if entry else None

    def _evict(self) -> None:
        now = time.time()
        stale = [k for k, v in self._data.items() if now - v.created > self._ttl]
        for k in stale:
            self._data.pop(k, None)
