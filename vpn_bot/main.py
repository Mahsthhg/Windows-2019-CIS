"""
Entry point — runs both customer bot and admin bot concurrently.
"""
import asyncio
import logging
import sys
from telegram.ext import Application
from config import CUSTOMER_BOT_TOKEN, ADMIN_BOT_TOKEN, ADMIN_CHAT_ID
from database import init_db
from customer_bot import setup_customer_bot
from admin_bot import setup_admin_bot

logging.basicConfig(
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def run() -> None:
    if CUSTOMER_BOT_TOKEN == "YOUR_CUSTOMER_BOT_TOKEN":
        logger.error("توکن ربات مشتری تنظیم نشده! فایل .env را بررسی کنید.")
        sys.exit(1)
    if ADMIN_BOT_TOKEN == "YOUR_ADMIN_BOT_TOKEN":
        logger.error("توکن ربات ادمین تنظیم نشده! فایل .env را بررسی کنید.")
        sys.exit(1)
    if ADMIN_CHAT_ID == 0:
        logger.error("ADMIN_CHAT_ID تنظیم نشده! فایل .env را بررسی کنید.")
        sys.exit(1)

    # Init DB
    init_db()
    logger.info("دیتابیس آماده شد.")

    # Build applications
    customer_app = Application.builder().token(CUSTOMER_BOT_TOKEN).build()
    admin_app    = Application.builder().token(ADMIN_BOT_TOKEN).build()

    # Cross-inject bot instances so each bot can message the other's users
    setup_customer_bot(customer_app, admin_bot_instance=admin_app.bot)
    setup_admin_bot(admin_app, customer_bot_instance=customer_app.bot)

    logger.info("ربات‌ها در حال راه‌اندازی هستند...")

    async with customer_app, admin_app:
        await customer_app.updater.start_polling(drop_pending_updates=True)
        await admin_app.updater.start_polling(drop_pending_updates=True)
        await customer_app.start()
        await admin_app.start()

        logger.info("✅ هر دو ربات در حال اجرا هستند!")
        logger.info("   ربات مشتری: آماده")
        logger.info("   ربات ادمین: آماده")
        logger.info("   برای توقف Ctrl+C بزنید.")

        # Block forever until SIGINT / SIGTERM
        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("بات متوقف شد.")
