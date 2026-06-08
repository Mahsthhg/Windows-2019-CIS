"""زمان‌بند خودکار: گزارش روزانه + یادآوری انقضا."""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import DAILY_REPORT_HOUR, EXPIRY_WARNING_DAYS, ADMIN_IDS

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Asia/Tehran")


def setup_scheduler(customer_bot_instance) -> AsyncIOScheduler:

    @scheduler.scheduled_job(CronTrigger(hour=DAILY_REPORT_HOUR, minute=0))
    async def daily_report():
        from database import get_stats
        from utils import fmt
        s = get_stats()
        avg_r = round(s.get("avg_rating", 0), 1)
        text = (
            "📊 *گزارش روزانه*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 امروز: {s['today_orders']} سفارش | {fmt(s['today_revenue'])}\n\n"
            f"👥 کل کاربران: {s['total_users']:,}\n"
            f"⏳ سفارش انتظار: {s['pending_orders']}\n"
            f"✅ تایید شده: {s['approved_orders']:,}\n"
            f"💰 درآمد کل: {fmt(s['total_revenue'])}\n"
            f"📦 گیگ فروش: {s['total_gb_sold']:,} GB\n"
            f"💬 تیکت باز: {s['open_tickets']}\n"
            f"⭐ میانگین امتیاز: {avg_r}/5"
        )
        for admin_id in ADMIN_IDS:
            try:
                await customer_bot_instance.send_message(admin_id, text, parse_mode="Markdown")
            except Exception as e:
                logger.error("Daily report to %s failed: %s", admin_id, e)

    @scheduler.scheduled_job(CronTrigger(hour=9, minute=30))
    async def expiry_reminder():
        from database import get_expiring_orders, mark_expiry_notified
        orders = get_expiring_orders(EXPIRY_WARNING_DAYS)
        for o in orders:
            try:
                await customer_bot_instance.send_message(
                    chat_id=o["user_id"],
                    text=(
                        f"⚠️ *یادآوری انقضا کانفیگ*\n\n"
                        f"کانفیگ سفارش *#{o['id']}* شما در "
                        f"*{EXPIRY_WARNING_DAYS} روز* دیگر منقضی می‌شود.\n"
                        f"📅 تاریخ انقضا: `{o['expiry_date']}`\n\n"
                        "برای تمدید روی 🛒 *خرید کانفیگ* بزنید."
                    ),
                    parse_mode="Markdown"
                )
                mark_expiry_notified(o["id"])
                logger.info("Expiry reminder sent for order #%s", o["id"])
            except Exception as e:
                logger.error("Expiry reminder to %s failed: %s", o["user_id"], e)

    return scheduler
