"""Small helpers shared across the bot."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# A permissive URL matcher used to extract links from free-form messages.
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


# Map a hostname fragment to a friendly platform name + emoji.
_PLATFORMS: list[tuple[tuple[str, ...], str]] = [
    (("youtube.com", "youtu.be"), "▶️ YouTube"),
    (("instagram.com", "instagr.am"), "📸 Instagram"),
    (("tiktok.com",), "🎵 TikTok"),
    (("pornhub.com", "xvideos.com", "xhamster.com", "xnxx.com", "redtube.com"), "🔞 Adult"),
    (("spotify.com",), "🎧 Spotify"),
    (("soundcloud.com",), "☁️ SoundCloud"),
    (("twitter.com", "x.com"), "🐦 X / Twitter"),
    (("facebook.com", "fb.watch"), "📘 Facebook"),
    (("twitch.tv",), "🎮 Twitch"),
    (("vimeo.com",), "🎬 Vimeo"),
    (("reddit.com",), "👽 Reddit"),
    (("dailymotion.com",), "📺 Dailymotion"),
    (("pinterest.com", "pin.it"), "📌 Pinterest"),
]


def find_urls(text: str | None) -> list[str]:
    """Return all http(s) URLs found in a piece of text."""
    if not text:
        return []
    return URL_RE.findall(text)


def first_url(text: str | None) -> str | None:
    urls = find_urls(text)
    return urls[0] if urls else None


def platform_name(url: str) -> str:
    """Return a friendly label for the URL's platform."""
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    for fragments, label in _PLATFORMS:
        if any(frag in host for frag in fragments):
            return label
    return f"🌐 {host or 'link'}"


def is_spotify(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return "spotify.com" in host or url.startswith("spotify:")


def human_size(num_bytes: float | None) -> str:
    """Format a byte count as a human-readable string."""
    if not num_bytes:
        return "?"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def human_duration(seconds: float | int | None) -> str:
    """Format a duration in seconds as H:MM:SS or M:SS."""
    if not seconds:
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def truncate(text: str, limit: int = 60) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


_MD_SPECIALS = r"_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Escape text for Telegram MarkdownV2."""
    return "".join("\\" + c if c in _MD_SPECIALS else c for c in str(text))
