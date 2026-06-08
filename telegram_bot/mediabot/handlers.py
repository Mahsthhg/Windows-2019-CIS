"""Telegram update handlers: commands, link detection, menus and callbacks."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from telegram import Message, Update
from telegram.constants import ChatAction, ChatType, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from . import admin, keyboards, texts, utils
from .config import Config
from .database import (
    AUDIO_QUALITY_CHOICES,
    DEFAULT_ACTION_CHOICES,
    VIDEO_QUALITY_CHOICES,
    Database,
    cache_key,
)
from .downloader import DownloadError, DownloadResult, Downloader

log = logging.getLogger(__name__)


# ───────────────────────── shared singletons ─────────────────────────
def _cfg(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.application.bot_data["config"]


def _dl(context: ContextTypes.DEFAULT_TYPE) -> Downloader:
    return context.application.bot_data["downloader"]


def _store(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["store"]


def _db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["db"]


def _bot_username(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.application.bot_data.get("bot_username", "")


def _html(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ───────────────────────── access gate ─────────────────────────
async def _missing_channels(
    context: ContextTypes.DEFAULT_TYPE, user_id: int, channels: list[str]
) -> list[str]:
    """Return channels the user has NOT joined (best-effort)."""
    missing: list[str] = []
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked"):
                missing.append(ch)
        except TelegramError:
            # Bot likely isn't an admin of that channel — don't lock users out.
            log.warning("Cannot check membership for %s", ch)
    return missing


async def _reply(update: Update, text: str, kb=None) -> None:
    msg = update.effective_message
    if msg is not None:
        await msg.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=kb,
            disable_web_page_preview=True,
        )


async def ensure_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Register the user and enforce ban / allow-list / force-join gates."""
    user = update.effective_user
    if user is None:
        return False

    db = _db(context)
    cfg = _cfg(context)
    await db.upsert_user(user.id, user.username, user.first_name)

    if await db.is_banned(user.id):
        await _reply(update, texts.BANNED)
        return False
    if not cfg.is_allowed(user.id):
        await _reply(update, texts.NOT_ALLOWED)
        return False
    if cfg.force_join and not cfg.is_admin(user.id):
        missing = await _missing_channels(context, user.id, cfg.force_join)
        if missing:
            await _reply(update, texts.FORCE_JOIN, kb=keyboards.force_join(missing))
            return False
    return True


# ───────────────────────── commands ─────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_access(update, context):
        return
    name = _html(update.effective_user.first_name or "دوست من")
    kb = keyboards.resolve_group_button(
        keyboards.main_menu(_cfg(context).is_admin(update.effective_user.id)),
        _bot_username(context),
    )
    await update.effective_message.reply_text(
        texts.START.format(name=name), parse_mode=ParseMode.HTML, reply_markup=kb
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_access(update, context):
        return
    await update.effective_message.reply_text(
        texts.HELP.format(max_mb=_cfg(context).max_filesize_mb),
        parse_mode=ParseMode.HTML, disable_web_page_preview=True,
        reply_markup=keyboards.back_to_menu(),
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_access(update, context):
        return
    s = await _db(context).get_settings(update.effective_user.id)
    await update.effective_message.reply_text(
        texts.SETTINGS.format(
            video=s["video_quality"], audio=s["audio_quality"],
            action=texts.ACTION_LABELS.get(s["default_action"], s["default_action"]),
        ),
        parse_mode=ParseMode.HTML, reply_markup=keyboards.settings_menu(s),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_access(update, context):
        return
    st = await _db(context).user_stats(update.effective_user.id)
    await update.effective_message.reply_text(
        texts.USER_STATS.format(total=st["total"], today=st["today"]),
        parse_mode=ParseMode.HTML, reply_markup=keyboards.back_to_menu(),
    )


async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _do_search(update, context, mode="menu")


async def cmd_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _do_search(update, context, mode="audio")


async def _do_search(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> None:
    if not await ensure_access(update, context):
        return
    query = " ".join(context.args) if context.args else ""
    if not query.strip():
        await update.effective_message.reply_text(texts.SEARCH_USAGE, parse_mode=ParseMode.HTML)
        return

    status = await update.effective_message.reply_text(
        texts.SEARCHING.format(q=_html(query)), parse_mode=ParseMode.HTML
    )
    try:
        results = await _dl(context).search(query, _cfg(context).search_results)
    except DownloadError as exc:
        await status.edit_text(texts.ERROR.format(err=_html(str(exc))), parse_mode=ParseMode.HTML)
        return

    if not results:
        await status.edit_text(texts.NO_RESULTS.format(q=_html(query)), parse_mode=ParseMode.HTML)
        return

    token = _store(context).put({"mode": mode, "results": results})
    header = texts.SEARCH_HEADER_MUSIC if mode == "audio" else texts.SEARCH_HEADER
    await status.edit_text(
        header, parse_mode=ParseMode.HTML,
        reply_markup=keyboards.search_results(token, results),
    )


async def cmd_dl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await ensure_access(update, context):
        return
    url = utils.first_url(" ".join(context.args) if context.args else "")
    if not url:
        await update.effective_message.reply_text(texts.SEND_LINK, parse_mode=ParseMode.HTML)
        return
    await _present_link(update, context, url)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("awaiting_broadcast", None)
    await update.effective_message.reply_text(texts.CANCELLED)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text: broadcast capture, link detection, or a nudge."""
    msg = update.effective_message
    if msg is None or not (msg.text or msg.caption):
        return

    # Admin broadcast capture takes priority.
    if context.user_data.get("awaiting_broadcast") and _cfg(context).is_admin(
        update.effective_user.id
    ):
        await admin.run_broadcast(update, context)
        return

    url = utils.first_url(msg.text or msg.caption)
    if not url:
        if update.effective_chat and update.effective_chat.type == ChatType.PRIVATE:
            await msg.reply_text(texts.SEND_LINK, parse_mode=ParseMode.HTML)
        return
    if not await ensure_access(update, context):
        return
    await _present_link(update, context, url)


async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    if any(m.id == context.bot.id for m in msg.new_chat_members):
        await msg.reply_text(texts.GROUP_WELCOME, parse_mode=ParseMode.HTML)


# ───────────────────────── link presentation ─────────────────────────
async def _present_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    msg = update.effective_message
    status = await msg.reply_text(texts.ANALYZING, parse_mode=ParseMode.HTML)

    if utils.is_spotify(url):
        token = _store(context).put({"url": url, "spotify": True})
        await status.edit_text(
            "🎧 لینک <b>Spotify</b> تشخیص داده شد.\n👇 برای دانلود بزن:",
            parse_mode=ParseMode.HTML, reply_markup=keyboards.spotify_actions(token),
        )
        return

    try:
        info = await _dl(context).probe(url)
    except DownloadError as exc:
        await status.edit_text(texts.ERROR.format(err=_html(str(exc))), parse_mode=ParseMode.HTML)
        return

    token = _store(context).put({"url": url, "info": info})
    await status.edit_text(
        keyboards.info_caption(info), parse_mode=ParseMode.HTML,
        disable_web_page_preview=True, reply_markup=keyboards.media_actions(token, info),
    )


# ───────────────────────── callback router ─────────────────────────
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    await query.answer()

    db = _db(context)
    cfg = _cfg(context)
    user = query.from_user
    await db.upsert_user(user.id, user.username, user.first_name)

    if await db.is_banned(user.id):
        await query.answer(texts.BANNED, show_alert=True)
        return
    if not cfg.is_allowed(user.id):
        await query.answer(texts.NOT_ALLOWED, show_alert=True)
        return

    data = query.data
    domain = data.split(":", 1)[0]

    if domain == "menu":
        await _on_menu(update, context)
        return
    if domain == "set":
        await _on_setting(update, context)
        return
    if domain == "adm":
        await admin.on_admin_callback(update, context)
        return
    if domain == "join":
        await _on_join_check(update, context)
        return

    await _on_media_callback(update, context)


async def _on_join_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    cfg = _cfg(context)
    missing = await _missing_channels(context, query.from_user.id, cfg.force_join)
    if missing:
        await query.answer(texts.FORCE_JOIN_FAIL, show_alert=True)
    else:
        await query.edit_message_text(texts.FORCE_JOIN_OK, parse_mode=ParseMode.HTML)


async def _on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    route = query.data.split(":", 1)[1]
    cfg = _cfg(context)
    uid = query.from_user.id

    if route == "home":
        kb = keyboards.resolve_group_button(
            keyboards.main_menu(cfg.is_admin(uid)), _bot_username(context)
        )
        await query.edit_message_text(texts.MAIN_MENU, parse_mode=ParseMode.HTML, reply_markup=kb)
    elif route == "help":
        await query.edit_message_text(
            texts.HELP.format(max_mb=cfg.max_filesize_mb), parse_mode=ParseMode.HTML,
            disable_web_page_preview=True, reply_markup=keyboards.back_to_menu(),
        )
    elif route == "about":
        await query.edit_message_text(
            texts.ABOUT, parse_mode=ParseMode.HTML, reply_markup=keyboards.back_to_menu()
        )
    elif route == "find":
        await query.edit_message_text(
            texts.SEARCH_USAGE, parse_mode=ParseMode.HTML, reply_markup=keyboards.back_to_menu()
        )
    elif route == "stats":
        st = await _db(context).user_stats(uid)
        await query.edit_message_text(
            texts.USER_STATS.format(total=st["total"], today=st["today"]),
            parse_mode=ParseMode.HTML, reply_markup=keyboards.back_to_menu(),
        )
    elif route == "settings":
        s = await _db(context).get_settings(uid)
        await query.edit_message_text(
            texts.SETTINGS.format(
                video=s["video_quality"], audio=s["audio_quality"],
                action=texts.ACTION_LABELS.get(s["default_action"], s["default_action"]),
            ),
            parse_mode=ParseMode.HTML, reply_markup=keyboards.settings_menu(s),
        )


async def _on_setting(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    key = query.data.split(":", 1)[1]
    db = _db(context)
    uid = query.from_user.id
    s = await db.get_settings(uid)

    if key == "vq":
        s["video_quality"] = utils.next_in_cycle(s["video_quality"], VIDEO_QUALITY_CHOICES)
        await db.set_setting(uid, "video_quality", s["video_quality"])
    elif key == "aq":
        s["audio_quality"] = utils.next_in_cycle(s["audio_quality"], AUDIO_QUALITY_CHOICES)
        await db.set_setting(uid, "audio_quality", s["audio_quality"])
    elif key == "act":
        s["default_action"] = utils.next_in_cycle(s["default_action"], DEFAULT_ACTION_CHOICES)
        await db.set_setting(uid, "default_action", s["default_action"])

    await query.edit_message_text(
        texts.SETTINGS.format(
            video=s["video_quality"], audio=s["audio_quality"],
            action=texts.ACTION_LABELS.get(s["default_action"], s["default_action"]),
        ),
        parse_mode=ParseMode.HTML, reply_markup=keyboards.settings_menu(s),
    )


async def _on_media_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts = query.data.split(":")
    action = parts[0]
    token = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else None

    if action == "x":
        try:
            await query.message.delete()
        except TelegramError:
            await _edit_safe(query, "بسته شد ✖️")
        return

    payload = _store(context).get(token)
    if payload is None:
        await _edit_safe(query, texts.EXPIRED)
        return

    if action == "q":
        await query.edit_message_reply_markup(reply_markup=keyboards.quality_menu(token))
        return
    if action == "back":
        info = payload.get("info")
        if info is not None:
            await query.edit_message_reply_markup(reply_markup=keyboards.media_actions(token, info))
        return
    if action == "dl":
        await _handle_search_pick(update, context, payload, extra)
        return

    url = payload.get("url")
    if not url:
        await _edit_safe(query, texts.EXPIRED)
        return

    settings = await _db(context).get_settings(query.from_user.id)

    if action == "a":
        await _run_and_deliver(update, context, "audio", url, settings)
    elif action == "v":
        vq = settings["video_quality"]
        height = None if vq == "best" else int(vq)
        await _run_and_deliver(update, context, "video", url, settings, max_height=height, quality=vq)
    elif action == "vh":
        height = int(extra) if extra and extra.isdigit() else None
        await _run_and_deliver(update, context, "video", url, settings, max_height=height, quality=str(height))
    elif action == "sp":
        await _run_and_deliver(update, context, "spotify", url, settings)


async def _handle_search_pick(
    update: Update, context: ContextTypes.DEFAULT_TYPE, payload: dict[str, Any], extra: str | None
) -> None:
    query = update.callback_query
    results = payload.get("results") or []
    idx = int(extra) if extra and extra.isdigit() else -1
    if idx < 0 or idx >= len(results):
        await _edit_safe(query, texts.EXPIRED)
        return
    chosen = results[idx]
    settings = await _db(context).get_settings(query.from_user.id)

    if payload.get("mode") == "audio":
        await _run_and_deliver(update, context, "audio", chosen.url, settings)
    else:
        try:
            info = await _dl(context).probe(chosen.url)
        except DownloadError as exc:
            await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
            return
        new_token = _store(context).put({"url": chosen.url, "info": info})
        await query.edit_message_text(
            keyboards.info_caption(info), parse_mode=ParseMode.HTML,
            disable_web_page_preview=True, reply_markup=keyboards.media_actions(new_token, info),
        )


# ───────────────────────── progress reporter ─────────────────────────
class _Progress:
    """Throttled, thread-safe bridge from yt-dlp's hook to a Telegram edit."""

    def __init__(self, loop, query, min_interval: float = 3.0):
        self._loop = loop
        self._query = query
        self._min = min_interval
        self._last = 0.0

    def __call__(self, d: dict[str, Any]) -> None:
        now = time.monotonic()
        if now - self._last < self._min:
            return
        self._last = now
        text = texts.PROGRESS.format(
            bar=utils.make_bar(d["percent"]),
            pct=d["percent"],
            done=utils.human_size(d["downloaded"]),
            total=utils.human_size(d["total"]),
            speed=utils.human_size(d["speed"]),
            eta=utils.human_duration(d["eta"]),
        )
        asyncio.run_coroutine_threadsafe(self._safe_edit(text), self._loop)

    async def _safe_edit(self, text: str) -> None:
        try:
            await self._query.edit_message_text(text, parse_mode=ParseMode.HTML)
        except TelegramError:
            pass


# ───────────────────────── download + deliver ─────────────────────────
async def _check_quota(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    cfg = _cfg(context)
    if cfg.daily_quota <= 0 or cfg.is_admin(user_id):
        return True
    used = await _db(context).downloads_last_24h(user_id)
    return used < cfg.daily_quota


async def _run_and_deliver(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    kind: str,
    url: str,
    settings: dict[str, Any],
    max_height: int | None = None,
    quality: str = "best",
) -> None:
    query = update.callback_query
    chat = update.effective_chat
    uid = query.from_user.id
    cfg = _cfg(context)
    db = _db(context)
    downloader = _dl(context)

    if not await _check_quota(context, uid):
        await _edit_safe(query, texts.QUOTA_REACHED.format(limit=cfg.daily_quota))
        return

    # Cache lookup (skip for live Spotify which we key as audio/spotify).
    quality_key = "spotify" if kind == "spotify" else (
        settings["audio_quality"] if kind == "audio" else quality
    )
    key = cache_key(url, "audio" if kind in ("audio", "spotify") else "video", quality_key)
    cached = await db.cache_get(key)
    if cached:
        await _edit_safe(query, texts.FROM_CACHE)
        if await _send_cached(update, context, cached):
            await db.record_download(uid, url, kind, quality_key, cached.get("title") or "", 0)
            await _delete_status(query)
            return
        await db.cache_invalidate(key)  # stale file_id; fall through to fresh

    try:
        await query.edit_message_text(texts.DOWNLOADING, parse_mode=ParseMode.HTML)
    except TelegramError:
        pass
    await _chat_action(context, chat.id, kind)

    loop = asyncio.get_running_loop()
    progress = _Progress(loop, query)

    try:
        if kind == "audio":
            result = await downloader.download_audio(url, settings["audio_quality"], progress)
        elif kind == "spotify":
            result = await downloader.download_spotify(url)
        else:
            result = await downloader.download_video(url, max_height=max_height, progress_cb=progress)
    except DownloadError as exc:
        await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
        return
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("Unexpected download failure")
        await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
        return

    try:
        sent = await _deliver(update, context, result)
        if sent is not None:
            file_id = _extract_file_id(sent)
            if file_id:
                await db.cache_put(
                    key, file_id, result.kind, result.title, result.duration or None
                )
            await db.record_download(uid, url, kind, quality_key, result.title, result.size)
    finally:
        _cleanup(result.path)


async def _send_cached(
    update: Update, context: ContextTypes.DEFAULT_TYPE, cached: dict[str, Any]
) -> bool:
    chat = update.effective_chat
    caption = f"<b>{_html(utils.truncate(cached.get('title') or '', 90))}</b>\n📥 @{_bot_username(context)}"
    try:
        if cached["file_type"] == "audio":
            await context.bot.send_audio(
                chat.id, audio=cached["file_id"], caption=caption,
                duration=cached.get("duration") or None, parse_mode=ParseMode.HTML,
            )
        else:
            await context.bot.send_video(
                chat.id, video=cached["file_id"], caption=caption,
                duration=cached.get("duration") or None, supports_streaming=True,
                parse_mode=ParseMode.HTML,
            )
        return True
    except TelegramError:
        return False


async def _deliver(
    update: Update, context: ContextTypes.DEFAULT_TYPE, result: DownloadResult
) -> Message | None:
    query = update.callback_query
    chat = update.effective_chat
    cfg = _cfg(context)

    if result.size > cfg.max_filesize_bytes:
        await _edit_safe(
            query,
            texts.TOO_BIG.format(size=utils.human_size(result.size), max_mb=cfg.max_filesize_mb),
        )
        return None

    try:
        await query.edit_message_text(texts.UPLOADING, parse_mode=ParseMode.HTML)
    except TelegramError:
        pass

    caption = f"<b>{_html(utils.truncate(result.title, 90))}</b>\n📥 @{_bot_username(context)}"
    try:
        with open(result.path, "rb") as fh:
            if result.kind == "audio":
                sent = await context.bot.send_audio(
                    chat_id=chat.id, audio=fh, title=utils.truncate(result.title, 64),
                    performer=result.uploader or None, duration=result.duration or None,
                    caption=caption, parse_mode=ParseMode.HTML,
                    read_timeout=120, write_timeout=120,
                )
            else:
                sent = await context.bot.send_video(
                    chat_id=chat.id, video=fh, duration=result.duration or None,
                    width=result.width or None, height=result.height or None,
                    caption=caption, parse_mode=ParseMode.HTML, supports_streaming=True,
                    read_timeout=180, write_timeout=180,
                )
    except TelegramError as exc:
        await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
        return None

    await _delete_status(query)
    return sent


def _extract_file_id(message: Message) -> str | None:
    if message.audio:
        return message.audio.file_id
    if message.video:
        return message.video.file_id
    if message.document:
        return message.document.file_id
    return None


async def _chat_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int, kind: str) -> None:
    action = ChatAction.UPLOAD_VOICE if kind in ("audio", "spotify") else ChatAction.UPLOAD_VIDEO
    try:
        await context.bot.send_chat_action(chat_id, action)
    except TelegramError:
        pass


async def _delete_status(query) -> None:
    try:
        await query.message.delete()
    except TelegramError:
        await _edit_safe(query, "✅ ارسال شد!")


async def _edit_safe(query, text: str) -> None:
    try:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except TelegramError:
        pass


def _cleanup(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
        parent = path.parent
        if parent.name.startswith("sp_"):
            for leftover in parent.glob("*"):
                try:
                    leftover.unlink()
                except OSError:
                    pass
            try:
                parent.rmdir()
            except OSError:
                pass
    except OSError:
        pass


# ───────────────────────── error handler ─────────────────────────
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Exception while handling an update:", exc_info=context.error)
