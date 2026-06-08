"""Entry point v2 — هر دو ربات + زمان‌بند + persistence."""
import asyncio
import logging
import sys
from telegram.ext import Application, PicklePersistence, PersistenceInput
from config import CUSTOMER_BOT_TOKEN, ADMIN_BOT_TOKEN, ADMIN_CHAT_ID, ADMIN_IDS
from database import init_db
from settings_manager import init_settings
from customer_bot import setup_customer_bot
from admin_bot import setup_admin_bot
from scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s | %(name)-24s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _check_config():
    errors = []
    if CUSTOMER_BOT_TOKEN == "YOUR_CUSTOMER_BOT_TOKEN":
        errors.append("CUSTOMER_BOT_TOKEN")
    if ADMIN_BOT_TOKEN == "YOUR_ADMIN_BOT_TOKEN":
        errors.append("ADMIN_BOT_TOKEN")
    if not ADMIN_IDS or ADMIN_IDS == [0]:
        errors.append("ADMIN_CHAT_ID / ADMIN_IDS")
    if errors:
        for e in errors:
            logger.error("❌ %s تنظیم نشده!", e)
        sys.exit(1)


async def run() -> None:
    _check_config()
    init_db()
    init_settings()
    logger.info("✅ دیتابیس و تنظیمات آماده شد.")

    # Holder lets post_init reference admin_app which is built after customer_app
    # bot_data=False: do not persist bot_data (Bot objects can't be pickled)
    # ConversationHandler state is stored separately, not affected by this
    customer_persistence = PicklePersistence(
        filepath="customer_state.pkl",
        store_data=PersistenceInput(bot_data=False),
    )
    customer_app = (
        Application.builder()
        .token(CUSTOMER_BOT_TOKEN)
        .persistence(customer_persistence)
        .connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30)
        .build()
    )
    admin_app = (
        Application.builder()
        .token(ADMIN_BOT_TOKEN)
        .connect_timeout(30).read_timeout(30).write_timeout(30).pool_timeout(30)
        .build()
    )

    setup_customer_bot(customer_app, admin_bot_instance=admin_app.bot)
    setup_admin_bot(admin_app, customer_bot_instance=customer_app.bot)

    sched = setup_scheduler(customer_app.bot)

    logger.info("🚀 در حال راه‌اندازی ربات‌ها...")

    async with customer_app, admin_app:
        await customer_app.updater.start_polling(drop_pending_updates=True)
        await admin_app.updater.start_polling(drop_pending_updates=True)
        await customer_app.start()
        await admin_app.start()
        sched.start()

        logger.info("✅ ربات مشتری: آماده")
        logger.info("✅ ربات ادمین:  آماده")
        logger.info("✅ زمان‌بند:    آماده")
        logger.info("   Ctrl+C برای توقف")

        await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("بات متوقف شد.")
