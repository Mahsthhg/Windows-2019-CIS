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

from . import handlers
from .config import Config, load_config
from .downloader import Downloader
from .store import JobStore

log = logging.getLogger(__name__)


def build_application(config: Config) -> Application:
    builder = ApplicationBuilder().token(config.token).concurrent_updates(True)

    # Optional self-hosted Bot API server (lifts the 50 MB upload limit).
    if config.base_url:
        builder = builder.base_url(config.base_url)
    if config.base_file_url:
        builder = builder.base_file_url(config.base_file_url)

    builder = builder.rate_limiter(AIORateLimiter())
    app = builder.build()

    # Shared singletons available to every handler via context.application.bot_data.
    app.bot_data["config"] = config
    app.bot_data["downloader"] = Downloader(config)
    app.bot_data["store"] = JobStore(ttl_seconds=3600)

    # Commands
    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("find", handlers.cmd_find))
    app.add_handler(CommandHandler("search", handlers.cmd_find))
    app.add_handler(CommandHandler("music", handlers.cmd_music))
    app.add_handler(CommandHandler(["dl", "download"], handlers.cmd_dl))

    # Greet groups when added
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handlers.on_new_members)
    )

    # Any text/caption that isn't a command -> look for a link
    app.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            handlers.on_message,
        )
    )

    # Glass-button callbacks
    app.add_handler(CallbackQueryHandler(handlers.on_callback))

    app.add_error_handler(handlers.on_error)
    app.post_init = _post_init
    return app


async def _post_init(app: Application) -> None:
    """Register the command menu shown in Telegram's UI."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "شروع و معرفی ربات"),
            BotCommand("find", "🔎 جستجوی آهنگ/ویدیو"),
            BotCommand("music", "🎵 جستجو و دانلود مستقیم MP3"),
            BotCommand("dl", "📎 دانلود از یک لینک"),
            BotCommand("help", "📖 راهنما"),
        ]
    )
    me = await app.bot.get_me()
    log.info("Bot started as @%s (id=%s)", me.username, me.id)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )
    # yt-dlp and httpx are noisy at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config = load_config()
    app = build_application(config)
    log.info("Starting bot … (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
