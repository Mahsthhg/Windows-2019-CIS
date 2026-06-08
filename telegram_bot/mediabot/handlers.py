"""Telegram update handlers: commands, link detection, and button callbacks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from . import keyboards, texts, utils
from .config import Config
from .downloader import DownloadError, DownloadResult, Downloader
from .store import JobStore

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Access to shared singletons stashed on the application
# --------------------------------------------------------------------------- #
def _cfg(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.application.bot_data["config"]


def _dl(context: ContextTypes.DEFAULT_TYPE) -> Downloader:
    return context.application.bot_data["downloader"]


def _store(context: ContextTypes.DEFAULT_TYPE) -> JobStore:
    return context.application.bot_data["store"]


def _html(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if the user is allowed to proceed (and warn if not)."""
    user = update.effective_user
    if user is None:
        return False
    if _cfg(context).is_allowed(user.id):
        return True
    if update.effective_message:
        await update.effective_message.reply_text(texts.NOT_ALLOWED)
    return False


# --------------------------------------------------------------------------- #
#  Commands
# --------------------------------------------------------------------------- #
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    name = _html(update.effective_user.first_name or "دوست من")
    await update.effective_message.reply_text(
        texts.START.format(name=name), parse_mode=ParseMode.HTML
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    await update.effective_message.reply_text(
        texts.HELP.format(max_mb=_cfg(context).max_filesize_mb),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _do_search(update, context, mode="menu")


async def cmd_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _do_search(update, context, mode="audio")


async def _do_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str
) -> None:
    if not await _guard(update, context):
        return
    query = " ".join(context.args) if context.args else ""
    if not query.strip():
        await update.effective_message.reply_text(
            texts.SEARCH_USAGE, parse_mode=ParseMode.HTML
        )
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
        await status.edit_text(
            texts.NO_RESULTS.format(q=_html(query)), parse_mode=ParseMode.HTML
        )
        return

    token = _store(context).put({"mode": mode, "results": results})
    header = "🎵 نتایج جستجو — یکی رو انتخاب کن:" if mode == "audio" else "🔎 نتایج جستجو:"
    await status.edit_text(
        header,
        reply_markup=keyboards.search_results(token, results),
    )


async def cmd_dl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update, context):
        return
    text = " ".join(context.args) if context.args else ""
    url = utils.first_url(text)
    if not url:
        await update.effective_message.reply_text(texts.SEND_LINK, parse_mode=ParseMode.HTML)
        return
    await _present_link(update, context, url)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Auto-detect a link in any text message (works in private & groups)."""
    msg = update.effective_message
    if msg is None or not (msg.text or msg.caption):
        return
    url = utils.first_url(msg.text or msg.caption)
    if not url:
        # In private chat, gently nudge; in groups stay silent.
        if update.effective_chat and update.effective_chat.type == "private":
            await msg.reply_text(texts.SEND_LINK, parse_mode=ParseMode.HTML)
        return
    if not await _guard(update, context):
        return
    await _present_link(update, context, url)


async def on_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the group when the bot itself is added."""
    msg = update.effective_message
    if not msg or not msg.new_chat_members:
        return
    me = context.bot.id
    if any(m.id == me for m in msg.new_chat_members):
        await msg.reply_text(texts.GROUP_WELCOME, parse_mode=ParseMode.HTML)


# --------------------------------------------------------------------------- #
#  Link presentation
# --------------------------------------------------------------------------- #
async def _present_link(
    update: Update, context: ContextTypes.DEFAULT_TYPE, url: str
) -> None:
    msg = update.effective_message
    status = await msg.reply_text(texts.ANALYZING, parse_mode=ParseMode.HTML)

    # Spotify needs a different (spotdl) path; show its dedicated button.
    if utils.is_spotify(url):
        token = _store(context).put({"url": url, "spotify": True})
        await status.edit_text(
            f"🎧 لینک <b>Spotify</b> تشخیص داده شد.\n👇 برای دانلود بزن:",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboards.spotify_actions(token),
        )
        return

    try:
        info = await _dl(context).probe(url)
    except DownloadError as exc:
        await status.edit_text(
            texts.ERROR.format(err=_html(str(exc))), parse_mode=ParseMode.HTML
        )
        return

    token = _store(context).put({"url": url, "info": info})
    await status.edit_text(
        keyboards.info_caption(info),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=keyboards.media_actions(token, info),
    )


# --------------------------------------------------------------------------- #
#  Callback router
# --------------------------------------------------------------------------- #
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or not query.data:
        return
    await query.answer()

    if not _cfg(context).is_allowed(query.from_user.id):
        await query.answer(texts.NOT_ALLOWED, show_alert=True)
        return

    parts = query.data.split(":")
    action = parts[0]
    token = parts[1] if len(parts) > 1 else ""
    extra = parts[2] if len(parts) > 2 else None

    if action == "x":
        try:
            await query.message.delete()
        except TelegramError:
            await query.edit_message_text("بسته شد ✖️")
        return

    payload = _store(context).get(token)
    if payload is None:
        await query.edit_message_text(texts.EXPIRED, parse_mode=ParseMode.HTML)
        return

    if action == "q":
        await query.edit_message_reply_markup(reply_markup=keyboards.quality_menu(token))
        return

    if action == "back":
        info = payload.get("info")
        if info is not None:
            await query.edit_message_reply_markup(
                reply_markup=keyboards.media_actions(token, info)
            )
        return

    if action == "dl":  # a search result was chosen
        await _handle_search_pick(update, context, payload, extra)
        return

    # Everything below downloads something for payload["url"].
    url = payload.get("url")
    if not url:
        await query.edit_message_text(texts.EXPIRED, parse_mode=ParseMode.HTML)
        return

    if action == "a":
        await _run_and_deliver(update, context, kind="audio", url=url)
    elif action == "v":
        await _run_and_deliver(update, context, kind="video", url=url)
    elif action == "vh":
        height = int(extra) if extra and extra.isdigit() else None
        await _run_and_deliver(update, context, kind="video", url=url, max_height=height)
    elif action == "sp":
        await _run_and_deliver(update, context, kind="spotify", url=url)


async def _handle_search_pick(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    payload: dict[str, Any],
    extra: str | None,
) -> None:
    query = update.callback_query
    results = payload.get("results") or []
    idx = int(extra) if extra and extra.isdigit() else -1
    if idx < 0 or idx >= len(results):
        await query.edit_message_text(texts.EXPIRED, parse_mode=ParseMode.HTML)
        return
    chosen = results[idx]

    if payload.get("mode") == "audio":
        # /music — go straight to MP3.
        await _run_and_deliver(update, context, kind="audio", url=chosen.url)
    else:
        # /find — show the audio/video action menu for the picked item.
        try:
            info = await _dl(context).probe(chosen.url)
        except DownloadError as exc:
            await query.edit_message_text(
                texts.ERROR.format(err=_html(str(exc))), parse_mode=ParseMode.HTML
            )
            return
        new_token = _store(context).put({"url": chosen.url, "info": info})
        await query.edit_message_text(
            keyboards.info_caption(info),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=keyboards.media_actions(new_token, info),
        )


# --------------------------------------------------------------------------- #
#  Download + deliver
# --------------------------------------------------------------------------- #
async def _run_and_deliver(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    kind: str,
    url: str,
    max_height: int | None = None,
) -> None:
    query = update.callback_query
    chat = update.effective_chat
    cfg = _cfg(context)
    downloader = _dl(context)

    try:
        await query.edit_message_text(texts.DOWNLOADING, parse_mode=ParseMode.HTML)
    except TelegramError:
        pass

    action = ChatAction.UPLOAD_VOICE if kind in ("audio", "spotify") else ChatAction.UPLOAD_VIDEO
    try:
        await context.bot.send_chat_action(chat.id, action)
    except TelegramError:
        pass

    try:
        if kind == "audio":
            result = await downloader.download_audio(url)
        elif kind == "spotify":
            result = await downloader.download_spotify(url)
        else:
            result = await downloader.download_video(url, max_height=max_height)
    except DownloadError as exc:
        await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
        return
    except Exception as exc:  # pragma: no cover - defensive
        log.exception("Unexpected download failure")
        await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
        return

    try:
        await _deliver(update, context, result)
    finally:
        _cleanup(result.path)


async def _deliver(
    update: Update, context: ContextTypes.DEFAULT_TYPE, result: DownloadResult
) -> None:
    query = update.callback_query
    chat = update.effective_chat
    cfg = _cfg(context)

    size = result.size
    if size > cfg.max_filesize_bytes:
        await _edit_safe(
            query,
            texts.TOO_BIG.format(
                size=utils.human_size(size), max_mb=cfg.max_filesize_mb
            ),
        )
        return

    try:
        await query.edit_message_text(texts.UPLOADING, parse_mode=ParseMode.HTML)
    except TelegramError:
        pass

    caption = f"<b>{_html(utils.truncate(result.title, 90))}</b>\n📥 @{(await context.bot.get_me()).username}"

    try:
        with open(result.path, "rb") as fh:
            if result.kind == "audio":
                await context.bot.send_audio(
                    chat_id=chat.id,
                    audio=fh,
                    title=utils.truncate(result.title, 64),
                    performer=result.uploader or None,
                    duration=result.duration or None,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    read_timeout=120,
                    write_timeout=120,
                )
            else:
                await context.bot.send_video(
                    chat_id=chat.id,
                    video=fh,
                    duration=result.duration or None,
                    width=result.width or None,
                    height=result.height or None,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                    read_timeout=180,
                    write_timeout=180,
                )
    except TelegramError as exc:
        await _edit_safe(query, texts.ERROR.format(err=_html(str(exc))))
        return

    # Success — remove the status message to keep the chat clean.
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
        # spotdl jobs live in their own folder — remove it if now empty.
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


# --------------------------------------------------------------------------- #
#  Global error handler
# --------------------------------------------------------------------------- #
async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Exception while handling an update:", exc_info=context.error)
