"""زمان‌بند — یادآور انقضا، گزارش روزانه، فلش‌سیل، قرعه‌کشی."""
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from config import ADMIN_IDS
import settings_manager as sm
from database import (
    get_expiring_orders, notif_sent, mark_notif_sent, get_stats,
    get_active_lottery, draw_lottery, get_lottery_entries, close_lottery,
    get_active_flash_sale, get_unnotified_flash_sales, mark_flash_notified,
    activate_flash_sale, deactivate_flash_sale, get_flash_sales,
    add_loyalty_points, get_all_users,
)
from utils import fmt, fmt_gb

logger = logging.getLogger(__name__)

# ─── Expiry reminders ─────────────────────────────────────────────────────────

async def check_expiring(bot):
    """Send reminders for orders expiring in 3d, 1d, today."""
    for days, key, emoji in [(3, "3d", "⚠️"), (1, "1d", "🔴"), (0, "0d", "💔")]:
        for order in get_expiring_orders(days):
            oid = order['id']
            uid = order['user_id']
            if notif_sent(oid, key):
                continue
            try:
                if days == 0:
                    msg = (f"💔 <b>سرویس شما منقضی شد!</b>\n\n"
                           f"🆔 سفارش #{oid} | 📦 {fmt_gb(order['gb_amount'])}\n\n"
                           "برای تمدید روی 🛒 <b>خرید کانفیگ</b> بزنید.")
                elif days == 1:
                    msg = (f"🔴 <b>فردا سرویس شما قطع می‌شود!</b>\n\n"
                           f"🆔 سفارش #{oid} | 📦 {fmt_gb(order['gb_amount'])}\n"
                           f"📅 انقضا: {order.get('expiry_date','—')[:10]}\n\n"
                           "همین الان تمدید کنید تا قطع نشوید.")
                else:
                    msg = (f"⚠️ <b>سرویس شما ۳ روز دیگر منقضی می‌شود</b>\n\n"
                           f"🆔 سفارش #{oid} | 📦 {fmt_gb(order['gb_amount'])}\n"
                           f"📅 انقضا: {order.get('expiry_date','—')[:10]}\n\n"
                           "برای تمدید آماده شوید.")
                await bot.send_message(uid, msg, parse_mode="HTML")
                mark_notif_sent(oid, key)
            except Exception as e:
                logger.warning("Expiry notify %s uid=%s: %s", key, uid, e)

# ─── Daily report ─────────────────────────────────────────────────────────────

async def daily_report(bot):
    if not sm.daily_report_enabled():
        return
    s = get_stats()
    text = (
        "📊 <b>گزارش روزانه</b>\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛍️ سفارش امروز: <b>{s['today_orders']}</b>\n"
        f"💰 درآمد امروز: <b>{fmt(s['today_revenue'])}</b>\n"
        f"📈 درآمد هفته: <b>{fmt(s['week_revenue'])}</b>\n"
        f"📈 درآمد ماه: <b>{fmt(s['month_revenue'])}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 کل کاربران: <b>{s['total_users']:,}</b>\n"
        f"⏳ در انتظار: <b>{s['pending_orders']}</b>\n"
        f"💬 تیکت باز: <b>{s['open_tickets']}</b>\n"
        f"💼 کیف پول‌ها: <b>{fmt(s['total_wallet'])}</b>"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, parse_mode="HTML")
        except Exception as e:
            logger.warning("Daily report to %s: %s", aid, e)

# ─── Flash sale automation ────────────────────────────────────────────────────

async def check_flash_sales(bot):
    from database import get_flash_sales
    # Notify upcoming sales
    for sale in get_unnotified_flash_sales():
        activate_flash_sale(sale['id'])
        mark_flash_notified(sale['id'])
        users = get_all_users()
        end_dt = datetime.fromisoformat(sale['ends_at'])
        hours = max(1, int((end_dt - datetime.now()).total_seconds() // 3600))
        text = (
            "🔥 <b>فلش سیل شروع شد!</b>\n\n"
            f"🎁 <b>{sale['name']}</b>\n"
            f"💸 تخفیف: <b>{sale['discount_pct']}٪</b>\n"
            f"⏰ تا <b>{hours} ساعت</b> دیگر\n\n"
            "همین الان بخرید! 🛒"
        )
        sent = 0
        for u in users:
            try:
                await bot.send_message(u['user_id'], text, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        logger.info("Flash sale broadcast: %d sent", sent)
        for aid in ADMIN_IDS:
            try:
                await bot.send_message(aid, f"🔥 فلش سیل شروع شد — {sent} نفر نوتیف گرفتن", parse_mode="HTML")
            except Exception:
                pass

    # Deactivate expired sales
    for sale in get_flash_sales():
        if not sale['is_active']:
            continue
        end_dt = datetime.fromisoformat(sale['ends_at'])
        if datetime.now() >= end_dt:
            deactivate_flash_sale(sale['id'])
            logger.info("Flash sale #%d ended", sale['id'])

# ─── Lottery automation ───────────────────────────────────────────────────────

async def check_lottery(bot):
    lottery = get_active_lottery()
    if not lottery:
        return
    draw_time = datetime.fromisoformat(lottery['draw_at'])
    if datetime.now() < draw_time:
        return
    entries = get_lottery_entries(lottery['id'])
    if not entries:
        close_lottery(lottery['id'])
        return
    winner = draw_lottery(lottery['id'])
    if not winner:
        return
    # Notify winner
    prize_text = ""
    if lottery['prize_gb']:
        prize_text += f"📦 <b>{lottery['prize_gb']} گیگابایت</b> رایگان"
    if lottery['prize_toman']:
        prize_text += f"\n💰 <b>{fmt(lottery['prize_toman'])}</b> شارژ کیف پول"
    # Give prize
    if lottery['prize_toman']:
        from database import admin_adjust_wallet
        admin_adjust_wallet(winner['user_id'], lottery['prize_toman'])
    try:
        await bot.send_message(
            winner['user_id'],
            f"🎉 <b>تبریک! شما برنده قرعه‌کشی شدید!</b>\n\n"
            f"🏆 قرعه‌کشی: {lottery['name']}\n"
            f"🎁 جایزه:\n{prize_text}\n\n"
            "جایزه به حسابتان اضافه شد.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning("Lottery winner notify: %s", e)
    # Notify admins
    wname = winner.get('full_name', '—')
    wuser = winner.get('username') or '—'
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid,
                f"🎰 <b>قرعه‌کشی پایان یافت</b>\n\n"
                f"🏆 {lottery['name']}\n"
                f"👥 شرکت‌کننده: {len(entries)}\n"
                f"🥇 برنده: {wname} (@{wuser})\n"
                f"🎁 جایزه: {prize_text}",
                parse_mode="HTML"
            )
        except Exception:
            pass
    logger.info("Lottery #%d drawn, winner: %s", lottery['id'], winner['user_id'])

# ─── Setup ────────────────────────────────────────────────────────────────────

def setup_scheduler(bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="Asia/Tehran")

    # Expiry reminders — every hour
    sched.add_job(check_expiring, IntervalTrigger(hours=1), args=[bot], id="expiry_check")

    # Flash sale check — every 5 minutes
    sched.add_job(check_flash_sales, IntervalTrigger(minutes=5), args=[bot], id="flash_check")

    # Lottery check — every 5 minutes
    sched.add_job(check_lottery, IntervalTrigger(minutes=5), args=[bot], id="lottery_check")

    # Daily report — 8:00 AM Tehran time
    sched.add_job(daily_report, CronTrigger(hour=8, minute=0), args=[bot], id="daily_report")

    return sched
