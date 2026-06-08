"""Inline keyboards ("glass buttons") and reusable UI text."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from . import texts, utils
from .downloader import MediaInfo, SearchResult

# Callback data: "action:token[:extra]".  Actions:
#   a   audio (MP3)            v   video (default quality)
#   q   open quality menu      vh  video at a given height
#   sp  spotify download       x   close/delete
#   dl  pick a search result   back  return to media menu
#   menu:* main-menu routes    set:* settings toggles
#   adm:* admin panel routes   join  re-check force-join


# ───────────────────────── Main menu ─────────────────────────
def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🔎 جستجوی آهنگ", callback_data="menu:find"),
            InlineKeyboardButton("📖 راهنما", callback_data="menu:help"),
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu:settings"),
            InlineKeyboardButton("📊 آمار من", callback_data="menu:stats"),
        ],
        [InlineKeyboardButton("ℹ️ درباره ربات", callback_data="menu:about")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("🛠 پنل مدیریت", callback_data="adm:panel")])
    rows.append(
        [
            InlineKeyboardButton(
                "➕ افزودن به گروه", url="https://t.me/{bot}?startgroup=true"
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def resolve_group_button(markup: InlineKeyboardMarkup, bot_username: str) -> InlineKeyboardMarkup:
    """Fill the {bot} placeholder in the 'add to group' URL once we know it."""
    new_rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            if btn.url and "{bot}" in btn.url:
                new_row.append(
                    InlineKeyboardButton(btn.text, url=btn.url.format(bot=bot_username))
                )
            else:
                new_row.append(btn)
        new_rows.append(new_row)
    return InlineKeyboardMarkup(new_rows)


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="menu:home")]]
    )


# ───────────────────────── Media actions ─────────────────────────
def media_actions(token: str, info: MediaInfo) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton("🎵 موزیک (MP3)", callback_data=f"a:{token}"),
            InlineKeyboardButton("🎬 ویدیو", callback_data=f"v:{token}"),
        ],
        [InlineKeyboardButton("📺 انتخاب کیفیت", callback_data=f"q:{token}")],
        [InlineKeyboardButton("✖️ بستن", callback_data=f"x:{token}")],
    ]
    return InlineKeyboardMarkup(rows)


def spotify_actions(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎧 دانلود از اسپاتیفای", callback_data=f"sp:{token}")],
            [InlineKeyboardButton("✖️ بستن", callback_data=f"x:{token}")],
        ]
    )


def quality_menu(token: str) -> InlineKeyboardMarkup:
    heights = [
        ("144p", 144), ("240p", 240), ("360p", 360),
        ("480p", 480), ("720p HD", 720), ("1080p FHD", 1080),
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


def search_results(token: str, results: list[SearchResult]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for i, r in enumerate(results):
        dur = utils.human_duration(r.duration) if r.duration else ""
        label = f"{i + 1}. {utils.truncate(r.title, 46)}"
        if dur:
            label += f"  · {dur}"
        rows.append([InlineKeyboardButton(label, callback_data=f"dl:{token}:{i}")])
    rows.append([InlineKeyboardButton("✖️ بستن", callback_data=f"x:{token}")])
    return InlineKeyboardMarkup(rows)


# ───────────────────────── Settings ─────────────────────────
def settings_menu(settings: dict) -> InlineKeyboardMarkup:
    vq = settings.get("video_quality", "best")
    aq = settings.get("audio_quality", "192")
    act = settings.get("default_action", "ask")
    rows = [
        [InlineKeyboardButton(f"🎬 کیفیت ویدیو: {vq}", callback_data="set:vq")],
        [InlineKeyboardButton(f"🎵 کیفیت صدا: {aq} kbps", callback_data="set:aq")],
        [
            InlineKeyboardButton(
                f"🎯 رفتار پیش‌فرض: {texts.ACTION_LABELS.get(act, act)}",
                callback_data="set:act",
            )
        ],
        [InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="menu:home")],
    ]
    return InlineKeyboardMarkup(rows)


# ───────────────────────── Admin ─────────────────────────
def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 بروزرسانی آمار", callback_data="adm:panel")],
            [InlineKeyboardButton("📢 پیام همگانی", callback_data="adm:broadcast")],
            [InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="menu:home")],
        ]
    )


# ───────────────────────── Force join ─────────────────────────
def force_join(channels: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        handle = ch.lstrip("@")
        rows.append(
            [InlineKeyboardButton(f"📢 عضویت در {ch}", url=f"https://t.me/{handle}")]
        )
    rows.append([InlineKeyboardButton("✅ عضو شدم", callback_data="join:check")])
    return InlineKeyboardMarkup(rows)


# ───────────────────────── Caption ─────────────────────────
def info_caption(info: MediaInfo) -> str:
    lines = [f"<b>{_html(utils.truncate(info.title, 90))}</b>"]
    meta: list[str] = []
    if info.uploader:
        meta.append(f"👤 {_html(utils.truncate(info.uploader, 40))}")
    if info.duration:
        meta.append(f"⏱ {utils.human_duration(info.duration)}")
    if info.is_playlist and info.playlist_count:
        meta.append(f"📚 {info.playlist_count} مورد")
    if meta:
        lines.append("  ·  ".join(meta))
    lines.append(f"\n{utils.platform_name(info.webpage_url or info.url)}")
    lines.append("\n👇 یکی از گزینه‌ها رو انتخاب کن:")
    return "\n".join(lines)


def _html(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
