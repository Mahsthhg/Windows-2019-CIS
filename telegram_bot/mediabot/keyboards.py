"""Inline keyboards ("glass buttons") and reusable UI text."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import utils
from .downloader import MediaInfo, SearchResult

# Callback data format: "action:token" where token is a short job id.
# Actions: a = audio, v = video (default), q = pick quality, vh = video@height,
#          sp = spotify, x = cancel/close, dl = search-pick


def media_actions(token: str, info: MediaInfo) -> InlineKeyboardMarkup:
    """Buttons shown after a link is detected."""
    rows = [
        [
            InlineKeyboardButton("🎵 موزیک (MP3)", callback_data=f"a:{token}"),
            InlineKeyboardButton("🎬 ویدیو", callback_data=f"v:{token}"),
        ],
        [
            InlineKeyboardButton("📺 انتخاب کیفیت", callback_data=f"q:{token}"),
        ],
        [InlineKeyboardButton("✖️ بستن", callback_data=f"x:{token}")],
    ]
    return InlineKeyboardMarkup(rows)


def spotify_actions(token: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🎧 دانلود از اسپاتیفای", callback_data=f"sp:{token}")],
        [InlineKeyboardButton("✖️ بستن", callback_data=f"x:{token}")],
    ]
    return InlineKeyboardMarkup(rows)


def quality_menu(token: str) -> InlineKeyboardMarkup:
    """Resolution picker for video downloads."""
    heights = [
        ("144p", 144),
        ("240p", 240),
        ("360p", 360),
        ("480p", 480),
        ("720p HD", 720),
        ("1080p FHD", 1080),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for label, h in heights:
        row.append(InlineKeyboardButton(f"📺 {label}", callback_data=f"vh:{token}:{h}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton("🎵 فقط صدا", callback_data=f"a:{token}"),
            InlineKeyboardButton("⬅️ برگشت", callback_data=f"back:{token}"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def search_results(token_prefix: str, results: list[SearchResult]) -> InlineKeyboardMarkup:
    """One button per search hit; callback carries the result index."""
    rows: list[list[InlineKeyboardButton]] = []
    for i, r in enumerate(results):
        dur = utils.human_duration(r.duration) if r.duration else ""
        label = f"{i + 1}. {utils.truncate(r.title, 48)}"
        if dur:
            label += f"  · {dur}"
        rows.append(
            [InlineKeyboardButton(label, callback_data=f"dl:{token_prefix}:{i}")]
        )
    rows.append([InlineKeyboardButton("✖️ بستن", callback_data=f"x:{token_prefix}")])
    return InlineKeyboardMarkup(rows)


def info_caption(info: MediaInfo) -> str:
    """Human-friendly summary shown alongside the action buttons."""
    lines = [f"<b>{_html(utils.truncate(info.title, 90))}</b>"]
    meta: list[str] = []
    if info.uploader:
        meta.append(f"👤 {_html(utils.truncate(info.uploader, 40))}")
    if info.duration:
        meta.append(f"⏱ {utils.human_duration(info.duration)}")
    if meta:
        lines.append("  ·  ".join(meta))
    lines.append(f"\n{utils.platform_name(info.webpage_url or info.url)}")
    lines.append("\n👇 یکی از گزینه‌ها رو انتخاب کن:")
    return "\n".join(lines)


def _html(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
