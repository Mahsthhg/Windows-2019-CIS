"""Application wiring and entry point."""

from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import admin, handlers
from .config import Config, load_config
from .database import Database
from .downloader import Downloader
from .store import JobStore

log = logging.getLogger(__name__)


def build_application(config: Config) -> Application:
    builder = ApplicationBuilder().token(config.token).concurrent_updates(True)

    if config.base_url:
        builder = builder.base_url(config.base_url)
    if config.base_file_url:
        builder = builder.base_file_url(config.base_file_url)

    builder = builder.rate_limiter(AIORateLimiter())
    builder = builder.post_init(_post_init).post_shutdown(_post_shutdown)
    app = builder.build()

    # Shared singletons available to every handler via context.application.bot_data.
    app.bot_data["config"] = config
    app.bot_data["downloader"] = Downloader(config)
    app.bot_data["store"] = JobStore(ttl_seconds=3600)
    app.bot_data["db"] = Database(config.db_path)

    # User commands
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler(["find", "search"], handlers.cmd_find))
    app.add_handler(CommandHandler("music", handlers.cmd_music))
    app.add_handler(CommandHandler(["dl", "download"], handlers.cmd_dl))
    app.add_handler(CommandHandler("settings", handlers.cmd_settings))
    app.add_handler(CommandHandler("stats", handlers.cmd_stats))
    app.add_handler(CommandHandler("cancel", handlers.cmd_cancel))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin.cmd_admin))
    app.add_handler(CommandHandler("broadcast", admin.cmd_broadcast))
    app.add_handler(CommandHandler("ban", admin.cmd_ban))
    app.add_handler(CommandHandler("unban", admin.cmd_unban))

    # Greet groups when added
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handlers.on_new_members)
    )

    # Any text/caption that isn't a command -> broadcast capture or link detection
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND, handlers.on_message
        )
    )

    # Glass-button callbacks (single router)
    app.add_handler(CallbackQueryHandler(handlers.on_callback))

    app.add_error_handler(handlers.on_error)
    return app


async def _post_init(app: Application) -> None:
    await app.bot_data["db"].connect()

    me = await app.bot.get_me()
    app.bot_data["bot_username"] = me.username

    await app.bot.set_my_commands(
        [
            BotCommand("start", "شروع و منوی اصلی"),
            BotCommand("find", "🔎 جستجوی آهنگ/ویدیو"),
            BotCommand("music", "🎵 جستجو و دانلود مستقیم MP3"),
            BotCommand("dl", "📎 دانلود از یک لینک"),
            BotCommand("settings", "⚙️ تنظیمات شخصی"),
            BotCommand("stats", "📊 آمار من"),
            BotCommand("help", "📖 راهنما"),
        ]
    )
    log.info("Bot started as @%s (id=%s)", me.username, me.id)


async def _post_shutdown(app: Application) -> None:
    db = app.bot_data.get("db")
    if db is not None:
        await db.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    app = build_application(config)
    log.info("Starting bot … (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
