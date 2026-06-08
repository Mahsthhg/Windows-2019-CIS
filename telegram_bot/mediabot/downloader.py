"""Download engine: wraps yt-dlp (and spotdl for Spotify) behind an async API."""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yt_dlp

from .config import Config

log = logging.getLogger(__name__)

# A progress callback receives a dict: {percent, downloaded, total, speed, eta}.
ProgressCB = Callable[[dict[str, Any]], None]


@dataclass
class MediaInfo:
    url: str
    title: str
    uploader: str | None = None
    duration: int | None = None
    thumbnail: str | None = None
    is_playlist: bool = False
    playlist_count: int = 0
    webpage_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    title: str
    url: str
    uploader: str | None = None
    duration: int | None = None


@dataclass
class DownloadResult:
    path: Path
    title: str
    kind: str  # "audio" or "video"
    duration: int | None = None
    uploader: str | None = None
    thumbnail: str | None = None
    width: int | None = None
    height: int | None = None

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0


class DownloadError(Exception):
    """Raised when extraction or download fails for a user-facing reason."""


class Downloader:
    """High-level, asyncio-friendly download helper."""

    def __init__(self, config: Config):
        self.config = config

    # ------------------------------------------------------------------ #
    #  yt-dlp option builders
    # ------------------------------------------------------------------ #
    def _base_opts(self) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "noplaylist": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "restrictfilenames": True,
            "geo_bypass": True,
        }
        if self.config.cookies_file:
            opts["cookiefile"] = self.config.cookies_file
        if self.config.proxy:
            opts["proxy"] = self.config.proxy
        return opts

    def _outtmpl(self, job_id: str) -> str:
        return str(self.config.download_dir / f"{job_id}.%(ext)s")

    @staticmethod
    def _hook(progress_cb: ProgressCB | None):
        if progress_cb is None:
            return None

        def hook(d: dict[str, Any]) -> None:
            if d.get("status") != "downloading":
                return
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100) if total else 0.0
            try:
                progress_cb(
                    {
                        "percent": percent,
                        "downloaded": downloaded,
                        "total": total,
                        "speed": d.get("speed") or 0,
                        "eta": d.get("eta") or 0,
                    }
                )
            except Exception:  # never let a UI hiccup kill the download
                pass

        return hook

    # ------------------------------------------------------------------ #
    #  Public async API
    # ------------------------------------------------------------------ #
    async def probe(self, url: str) -> MediaInfo:
        return await asyncio.to_thread(self._probe_sync, url)

    async def search(self, query: str, limit: int) -> list[SearchResult]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    async def download_audio(
        self, url: str, bitrate: str = "192", progress_cb: ProgressCB | None = None
    ) -> DownloadResult:
        return await asyncio.to_thread(self._download_audio_sync, url, bitrate, progress_cb)

    async def download_video(
        self,
        url: str,
        max_height: int | None = None,
        progress_cb: ProgressCB | None = None,
    ) -> DownloadResult:
        return await asyncio.to_thread(
            self._download_video_sync, url, max_height, progress_cb
        )

    async def download_spotify(self, url: str) -> DownloadResult:
        return await asyncio.to_thread(self._download_spotify_sync, url)

    # ------------------------------------------------------------------ #
    #  Synchronous implementations (run in a worker thread)
    # ------------------------------------------------------------------ #
    def _probe_sync(self, url: str) -> MediaInfo:
        opts = self._base_opts()
        opts["noplaylist"] = True
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError(_clean_error(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise DownloadError(f"Could not read this link: {exc}") from exc

        if info is None:
            raise DownloadError("No media found at this link.")

        if "entries" in info:  # a playlist/collection
            entries = [e for e in info["entries"] if e]
            first = entries[0] if entries else {}
            return MediaInfo(
                url=url,
                title=info.get("title") or first.get("title") or "Playlist",
                uploader=info.get("uploader"),
                is_playlist=True,
                playlist_count=len(entries),
                thumbnail=first.get("thumbnail"),
                webpage_url=info.get("webpage_url") or url,
                raw=info,
            )

        return MediaInfo(
            url=url,
            title=info.get("title") or "media",
            uploader=info.get("uploader") or info.get("channel"),
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
            webpage_url=info.get("webpage_url") or url,
            raw=info,
        )

    def _search_sync(self, query: str, limit: int) -> list[SearchResult]:
        opts = self._base_opts()
        opts.update({"extract_flat": True, "noplaylist": True})
        search_url = f"ytsearch{max(1, limit)}:{query}"
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(search_url, download=False)
        except Exception as exc:
            raise DownloadError(f"Search failed: {exc}") from exc

        results: list[SearchResult] = []
        for entry in (info or {}).get("entries", []) or []:
            if not entry:
                continue
            results.append(
                SearchResult(
                    title=entry.get("title") or "Unknown",
                    url=entry.get("url") or entry.get("webpage_url") or "",
                    uploader=entry.get("uploader") or entry.get("channel"),
                    duration=entry.get("duration"),
                )
            )
        return [r for r in results if r.url]

    def _download_audio_sync(
        self, url: str, bitrate: str, progress_cb: ProgressCB | None
    ) -> DownloadResult:
        job_id = uuid.uuid4().hex
        opts = self._base_opts()
        opts.update(
            {
                "format": "bestaudio/best",
                "outtmpl": self._outtmpl(job_id),
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": bitrate,
                    },
                    {"key": "FFmpegMetadata"},
                    {"key": "EmbedThumbnail"},
                ],
                "writethumbnail": True,
            }
        )
        hook = self._hook(progress_cb)
        if hook:
            opts["progress_hooks"] = [hook]
        info = self._run_download(opts, url)
        path = self._find_output(job_id, prefer=(".mp3", ".m4a", ".opus", ".webm"))
        return DownloadResult(
            path=path,
            title=info.get("title") or path.stem,
            kind="audio",
            duration=info.get("duration"),
            uploader=info.get("uploader") or info.get("channel") or info.get("artist"),
            thumbnail=info.get("thumbnail"),
        )

    def _download_video_sync(
        self, url: str, max_height: int | None, progress_cb: ProgressCB | None
    ) -> DownloadResult:
        job_id = uuid.uuid4().hex
        opts = self._base_opts()

        if max_height:
            fmt = (
                f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
                f"best[height<={max_height}][ext=mp4]/"
                f"best[height<={max_height}]/best"
            )
        else:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        opts.update(
            {
                "format": fmt,
                "outtmpl": self._outtmpl(job_id),
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegMetadata"}],
            }
        )
        hook = self._hook(progress_cb)
        if hook:
            opts["progress_hooks"] = [hook]
        info = self._run_download(opts, url)
        path = self._find_output(job_id, prefer=(".mp4", ".mkv", ".webm"))
        return DownloadResult(
            path=path,
            title=info.get("title") or path.stem,
            kind="video",
            duration=info.get("duration"),
            uploader=info.get("uploader") or info.get("channel"),
            thumbnail=info.get("thumbnail"),
            width=info.get("width"),
            height=info.get("height"),
        )

    def _download_spotify_sync(self, url: str) -> DownloadResult:
        spotdl_bin = shutil.which("spotdl")
        if not spotdl_bin:
            raise DownloadError(
                "Spotify support needs the 'spotdl' package. "
                "Install it with: pip install spotdl"
            )

        job_dir = self.config.download_dir / f"sp_{uuid.uuid4().hex}"
        job_dir.mkdir(parents=True, exist_ok=True)

        import subprocess

        cmd = [
            spotdl_bin,
            "download",
            url,
            "--output",
            str(job_dir / "{artists} - {title}.{output-ext}"),
            "--format",
            "mp3",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired as exc:
            raise DownloadError("Spotify download timed out.") from exc

        files = sorted(job_dir.glob("*.mp3"))
        if not files:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            tail = detail[-1] if detail else "no audio produced"
            raise DownloadError(f"Spotify download failed: {tail}")

        path = files[0]
        return DownloadResult(path=path, title=path.stem, kind="audio")

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    def _run_download(self, opts: dict[str, Any], url: str) -> dict[str, Any]:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError(_clean_error(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise DownloadError(f"Download failed: {exc}") from exc
        if info is None:
            raise DownloadError("Nothing could be downloaded from this link.")
        if "entries" in info:  # took the first item of a collection
            entries = [e for e in info["entries"] if e]
            info = entries[0] if entries else info
        return info

    def _find_output(self, job_id: str, prefer: tuple[str, ...]) -> Path:
        candidates = sorted(self.config.download_dir.glob(f"{job_id}.*"))
        media = [
            p
            for p in candidates
            if p.suffix.lower() not in (".jpg", ".png", ".webp", ".part", ".ytdl")
        ]
        if not media:
            media = candidates
        if not media:
            raise DownloadError("The download finished but no file was found.")
        for ext in prefer:
            for p in media:
                if p.suffix.lower() == ext:
                    return p
        return media[0]


def _clean_error(exc: Exception) -> str:
    """Turn a noisy yt-dlp error into a short, user-friendly message."""
    msg = str(exc).replace("ERROR:", "").strip()
    lowered = msg.lower()
    if "private" in lowered:
        return "این محتوا خصوصی است و قابل دانلود نیست."
    if "age" in lowered and "restrict" in lowered:
        return "این محتوا محدودیت سنی دارد و به فایل کوکی نیاز است."
    if "unavailable" in lowered:
        return "این محتوا در دسترس نیست یا حذف شده است."
    if "unsupported url" in lowered:
        return "این سایت/لینک پشتیبانی نمی‌شود."
    if "login" in lowered or "sign in" in lowered:
        return "این محتوا نیازمند ورود به حساب است (فایل کوکی لازم است)."
    return msg.splitlines()[0][:300] if msg else "دانلود ناموفق بود."
