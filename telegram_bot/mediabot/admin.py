"""Admin-only commands and callbacks: panel, stats, broadcast, ban/unban."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from . import keyboards, texts

log = logging.getLogger(__name__)


def _cfg(context):
    return context.application.bot_data["config"]


def _db(context):
    return context.application.bot_data["db"]


def _is_admin(update: Update, context) -> bool:
    user = update.effective_user
    return user is not None and _cfg(context).is_admin(user.id)


# ───────────────────────── commands ─────────────────────────
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update, context):
        await update.effective_message.reply_text(texts.ADMIN_ONLY)
        return
    stats = await _db(context).global_stats()
    await update.effective_message.reply_text(
        texts.ADMIN_PANEL.format(**stats),
        parse_mode=ParseMode.HTML, reply_markup=keyboards.admin_menu(),
    )


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update, context):
        await update.effective_message.reply_text(texts.ADMIN_ONLY)
        return
    context.user_data["awaiting_broadcast"] = True
    await update.effective_message.reply_text(
        texts.ADMIN_BROADCAST_ASK, parse_mode=ParseMode.HTML
    )


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ban_common(update, context, banned=True)


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ban_common(update, context, banned=False)


async def _ban_common(update: Update, context: ContextTypes.DEFAULT_TYPE, banned: bool) -> None:
    if not _is_admin(update, context):
        await update.effective_message.reply_text(texts.ADMIN_ONLY)
        return
    args = context.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text(texts.ADMIN_BAN_USAGE, parse_mode=ParseMode.HTML)
        return
    uid = int(args[0])
    db = _db(context)
    await db.upsert_user(uid, None, None)
    await db.set_banned(uid, banned)
    tmpl = texts.ADMIN_BANNED_OK if banned else texts.ADMIN_UNBANNED_OK
    await update.effective_message.reply_text(tmpl.format(uid=uid), parse_mode=ParseMode.HTML)


# ───────────────────────── broadcast runner ─────────────────────────
async def run_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forward the admin's next message to every (non-banned) user."""
    context.user_data.pop("awaiting_broadcast", None)
    src = update.effective_message
    db = _db(context)
    user_ids = await db.all_user_ids()

    status = await src.reply_text(
        texts.ADMIN_BROADCAST_RUNNING.format(n=len(user_ids)), parse_mode=ParseMode.HTML
    )

    ok = fail = 0
    for i, uid in enumerate(user_ids):
        try:
            await src.copy(chat_id=uid)
            ok += 1
        except TelegramError:
            fail += 1
        # Stay well under Telegram's ~30 msg/sec broadcast limit.
        if i % 20 == 19:
            await asyncio.sleep(1)

    await status.edit_text(
        texts.ADMIN_BROADCAST_DONE.format(ok=ok, fail=fail), parse_mode=ParseMode.HTML
    )


# ───────────────────────── callbacks ─────────────────────────
async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not _cfg(context).is_admin(query.from_user.id):
        await query.answer(texts.ADMIN_ONLY, show_alert=True)
        return
    route = query.data.split(":", 1)[1]

    if route == "panel":
        stats = await _db(context).global_stats()
        await query.edit_message_text(
            texts.ADMIN_PANEL.format(**stats),
            parse_mode=ParseMode.HTML, reply_markup=keyboards.admin_menu(),
        )
    elif route == "broadcast":
        context.user_data["awaiting_broadcast"] = True
        await query.edit_message_text(texts.ADMIN_BROADCAST_ASK, parse_mode=ParseMode.HTML)
