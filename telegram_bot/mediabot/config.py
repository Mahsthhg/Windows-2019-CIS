"""Configuration loaded from environment variables / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (telegram_bot/) if present.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


def _csv_ints(raw: str | None) -> set[int]:
    """Parse a comma-separated list of integers into a set."""
    if not raw:
        return set()
    out: set[int] = set()
    for piece in raw.split(","):
        piece = piece.strip()
        if piece.lstrip("-").isdigit():
            out.add(int(piece))
    return out


@dataclass
class Config:
    token: str
    admins: set[int] = field(default_factory=set)
    allowed_users: set[int] = field(default_factory=set)
    max_filesize_mb: int = 49
    search_results: int = 6
    download_dir: Path = Path("downloads")
    base_url: str | None = None
    base_file_url: str | None = None
    cookies_file: str | None = None
    proxy: str | None = None

    @property
    def max_filesize_bytes(self) -> int:
        return self.max_filesize_mb * 1024 * 1024

    def is_allowed(self, user_id: int) -> bool:
        """Return True if the user may use the bot."""
        if not self.allowed_users:
            return True
        return user_id in self.allowed_users or user_id in self.admins

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admins


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "BOT_TOKEN is not set. Copy .env.example to .env and add your "
            "token from @BotFather."
        )

    download_dir = Path(os.getenv("DOWNLOAD_DIR", "downloads")).expanduser()
    download_dir.mkdir(parents=True, exist_ok=True)

    cookies = os.getenv("COOKIES_FILE", "").strip() or None
    if cookies and not Path(cookies).exists():
        cookies = None  # silently ignore a missing cookies file

    return Config(
        token=token,
        admins=_csv_ints(os.getenv("ADMINS")),
        allowed_users=_csv_ints(os.getenv("ALLOWED_USERS")),
        max_filesize_mb=int(os.getenv("MAX_FILESIZE_MB", "49") or "49"),
        search_results=int(os.getenv("SEARCH_RESULTS", "6") or "6"),
        download_dir=download_dir,
        base_url=os.getenv("BASE_URL", "").strip() or None,
        base_file_url=os.getenv("BASE_FILE_URL", "").strip() or None,
        cookies_file=cookies,
        proxy=os.getenv("PROXY", "").strip() or None,
    )
