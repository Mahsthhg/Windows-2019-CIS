"""
Admin management Telegram bot.
Handles: order approval/rejection, support replies,
         broadcasts, statistics, user management, discount codes.
"""
import logging
import re
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes,
)
from config import ADMIN_CHAT_ID, PRICE_PER_GB, BOT_NAME
from database import (
    get_order, get_pending_orders, get_all_users,
    get_user, approve_order, reject_order,
    get_stats, close_ticket, get_ticket,
    block_user, unblock_user, create_discount_code,
)
from keyboards import admin_main_kb, admin_cancel_kb, admin_new_order_kb

logger = logging.getLogger(__name__)

# ─── Admin state keys (stored in context.user_data) ──────────────────────────
STATE         = "adm_state"
PENDING_ORDER = "adm_pending_order"
PENDING_CONFIG= "adm_pending_config"

S_IDLE              = "idle"
S_WAIT_CONFIG       = "wait_config"
S_WAIT_SUB          = "wait_sub"
S_WAIT_REJECT_NOTE  = "wait_reject_note"
S_WAIT_BROADCAST    = "wait_broadcast"
S_WAIT_DISCOUNT     = "wait_discount"

def fmt_price(p: int) -> str:
    return f"{p:,} تومان"

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_CHAT_ID


# ─── Guard decorator ──────────────────────────────────────────────────────────

def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_admin(uid):
            await update.effective_message.reply_text("⛔ شما دسترسی ادمین ندارید.")
            return
        return await func(update, context)
    return wrapper


# ─── /start ───────────────────────────────────────────────────────────────────

@admin_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE] = S_IDLE
    await update.message.reply_text(
        f"👑 *پنل مدیریت — {BOT_NAME}*\n\n"
        "به ربات ادمین خوش آمدید.\n"
        "سفارشات جدید به صورت خودکار اینجا ارسال می‌شوند.",
        parse_mode="Markdown",
        reply_markup=admin_main_kb()
    )


# ─── Inline callback handler (order approve/reject buttons) ───────────────────

@admin_only
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "adm_cancel":
        context.user_data[STATE] = S_IDLE
        await query.message.reply_text("❌ عملیات لغو شد.", reply_markup=admin_main_kb())
        return

    # ── Approve order ──
    if data.startswith("adm_approve_"):
        order_id = int(data.split("_")[2])
        order = get_order(order_id)
        if not order:
            await query.message.reply_text("❌ سفارش پیدا نشد.")
            return
        if order["status"] != "pending":
            await query.message.reply_text(f"⚠️ سفارش #{order_id} قبلاً پردازش شده.")
            return

        context.user_data[STATE]         = S_WAIT_CONFIG
        context.user_data[PENDING_ORDER] = order_id

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"✅ سفارش *#{order_id}* در حال تایید است.\n\n"
            "📤 لطفاً کانفیگ VLESS را ارسال کنید:\n"
            "(یا /cancel برای لغو)",
            parse_mode="Markdown",
            reply_markup=admin_cancel_kb()
        )

    # ── Reject order ──
    elif data.startswith("adm_reject_"):
        order_id = int(data.split("_")[2])
        order = get_order(order_id)
        if not order:
            await query.message.reply_text("❌ سفارش پیدا نشد.")
            return
        if order["status"] != "pending":
            await query.message.reply_text(f"⚠️ سفارش #{order_id} قبلاً پردازش شده.")
            return

        context.user_data[STATE]         = S_WAIT_REJECT_NOTE
        context.user_data[PENDING_ORDER] = order_id

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(
            f"❌ دلیل رد سفارش *#{order_id}* را وارد کنید:\n"
            "(یا - برای رد بدون دلیل)\n"
            "(یا /cancel برای لغو)",
            parse_mode="Markdown",
            reply_markup=admin_cancel_kb()
        )

    # ── User profile ──
    elif data.startswith("adm_profile_"):
        order_id = int(data.split("_")[2])
        order = get_order(order_id)
        if not order:
            await query.message.reply_text("❌ سفارش پیدا نشد.")
            return
        user = get_user(order["user_id"])
        if not user:
            await query.message.reply_text("❌ کاربر پیدا نشد.")
            return
        uname = f"@{user['username']}" if user.get("username") else "—"
        text = (
            f"👤 *پروفایل کاربر*\n\n"
            f"🆔 آیدی: `{user['user_id']}`\n"
            f"👤 نام: {user['full_name']}\n"
            f"🔗 یوزرنیم: {uname}\n"
            f"📅 تاریخ عضویت: {user['join_date'][:10]}\n"
            f"🛍️ تعداد سفارشات: {user['total_orders']}\n"
            f"💰 کل خرید: {fmt_price(user['total_spent'])}\n"
            f"🚫 مسدود: {'بله' if user['is_blocked'] else 'خیر'}"
        )
        await query.message.reply_text(text, parse_mode="Markdown")


# ─── Text message handler ─────────────────────────────────────────────────────

@admin_only
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    state = context.user_data.get(STATE, S_IDLE)

    # ── Await config ──
    if state == S_WAIT_CONFIG:
        context.user_data[PENDING_CONFIG] = text
        context.user_data[STATE] = S_WAIT_SUB
        await update.message.reply_text(
            "🔗 لطفاً لینک Subscription را ارسال کنید:\n"
            "(یا `-` اگر ندارید)",
            reply_markup=admin_cancel_kb()
        )
        return

    # ── Await sub link ──
    if state == S_WAIT_SUB:
        order_id = context.user_data.get(PENDING_ORDER)
        config   = context.user_data.get(PENDING_CONFIG, "")
        sub_link = "" if text.strip() == "-" else text.strip()

        order = get_order(order_id)
        if not order:
            await update.message.reply_text("❌ سفارش پیدا نشد.")
            context.user_data[STATE] = S_IDLE
            return

        approve_order(order_id, config, sub_link)

        # Send config to customer
        customer_bot: Bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            await _deliver_config_to_customer(customer_bot, order, config, sub_link)

        await update.message.reply_text(
            f"✅ سفارش *#{order_id}* تایید شد و کانفیگ برای مشتری ارسال گردید.",
            parse_mode="Markdown",
            reply_markup=admin_main_kb()
        )
        context.user_data[STATE] = S_IDLE
        context.user_data.pop(PENDING_ORDER, None)
        context.user_data.pop(PENDING_CONFIG, None)
        return

    # ── Await reject note ──
    if state == S_WAIT_REJECT_NOTE:
        order_id = context.user_data.get(PENDING_ORDER)
        note = "" if text.strip() == "-" else text.strip()

        order = get_order(order_id)
        if not order:
            await update.message.reply_text("❌ سفارش پیدا نشد.")
            context.user_data[STATE] = S_IDLE
            return

        reject_order(order_id, note)

        customer_bot: Bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            reason_line = f"\n\n❗ دلیل: {note}" if note else ""
            try:
                await customer_bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"❌ سفارش *#{order_id}* رد شد.{reason_line}\n\n"
                        "در صورت نیاز به پشتیبانی مراجعه کنید."
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error("Failed to notify customer: %s", e)

        await update.message.reply_text(
            f"❌ سفارش *#{order_id}* رد شد.",
            parse_mode="Markdown",
            reply_markup=admin_main_kb()
        )
        context.user_data[STATE] = S_IDLE
        context.user_data.pop(PENDING_ORDER, None)
        return

    # ── Await broadcast ──
    if state == S_WAIT_BROADCAST:
        users = get_all_users()
        sent = 0
        failed = 0
        customer_bot: Bot = context.bot_data.get("customer_bot_instance")
        if customer_bot:
            for u in users:
                try:
                    await customer_bot.send_message(u["user_id"], text, parse_mode="Markdown")
                    sent += 1
                except Exception:
                    failed += 1

        await update.message.reply_text(
            f"📢 پیام همگانی ارسال شد.\n"
            f"✅ موفق: {sent}\n❌ ناموفق: {failed}",
            reply_markup=admin_main_kb()
        )
        context.user_data[STATE] = S_IDLE
        return

    # ── Await discount code creation ──
    if state == S_WAIT_DISCOUNT:
        parts = text.strip().split()
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ فرمت اشتباه. ارسال کنید:\n`CODE PERCENT [MAX_USES]`\nمثال: `PROMO10 10 50`",
                parse_mode="Markdown"
            )
            return
        code = parts[0].upper()
        try:
            pct  = int(parts[1])
            uses = int(parts[2]) if len(parts) > 2 else 1
        except ValueError:
            await update.message.reply_text("❌ عدد نامعتبر.")
            return
        create_discount_code(code, pct, uses)
        await update.message.reply_text(
            f"✅ کد تخفیف *{code}* با {pct}٪ تخفیف (max {uses} استفاده) ایجاد شد.",
            parse_mode="Markdown",
            reply_markup=admin_main_kb()
        )
        context.user_data[STATE] = S_IDLE
        return

    # ── Menu buttons ──
    if text == "📊 آمار کلی":
        await show_stats(update, context)
    elif text == "📋 سفارشات در انتظار":
        await show_pending(update, context)
    elif text == "📢 پیام همگانی":
        context.user_data[STATE] = S_WAIT_BROADCAST
        await update.message.reply_text(
            "📢 پیام همگانی را ارسال کنید:\n(از Markdown پشتیبانی می‌شود)\n(یا /cancel)",
            reply_markup=admin_cancel_kb()
        )
    elif text == "👥 مدیریت کاربران":
        await show_users(update, context)
    elif text == "🎫 ایجاد کد تخفیف":
        context.user_data[STATE] = S_WAIT_DISCOUNT
        await update.message.reply_text(
            "🎫 کد تخفیف جدید\n\n"
            "فرمت: `CODE PERCENT [MAX_USES]`\n"
            "مثال: `VIP20 20 10`\n"
            "(یا /cancel)",
            parse_mode="Markdown",
            reply_markup=admin_cancel_kb()
        )
    elif text == "💰 گزارش درآمد":
        await show_revenue(update, context)
    elif text == "🎫 تیکت‌های باز":
        await show_open_tickets(update, context)
    elif text == "⚙️ راهنما":
        await show_help(update, context)


# ─── /reply_<ticket_id> ───────────────────────────────────────────────────────

@admin_only
async def cmd_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    match = re.match(r"^/reply_(\d+)(?:\s+(.+))?$", update.message.text, re.DOTALL)
    if not match:
        await update.message.reply_text("فرمت: /reply_ID متن پاسخ")
        return

    ticket_id = int(match.group(1))
    reply_text = match.group(2) or ""

    if not reply_text.strip():
        await update.message.reply_text("لطفاً متن پاسخ را وارد کنید:\n/reply_ID متن")
        return

    user_id = close_ticket(ticket_id, reply_text)
    if not user_id:
        await update.message.reply_text("❌ تیکت پیدا نشد.")
        return

    customer_bot: Bot = context.bot_data.get("customer_bot_instance")
    if customer_bot:
        try:
            await customer_bot.send_message(
                chat_id=user_id,
                text=(
                    f"💬 *پاسخ پشتیبانی — تیکت #{ticket_id}*\n\n"
                    f"{reply_text}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Reply delivery failed: %s", e)

    await update.message.reply_text(
        f"✅ پاسخ تیکت #{ticket_id} ارسال شد.",
        reply_markup=admin_main_kb()
    )


# ─── /cancel ─────────────────────────────────────────────────────────────────

@admin_only
async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data[STATE] = S_IDLE
    await update.message.reply_text("❌ لغو شد.", reply_markup=admin_main_kb())


# ─── /block and /unblock ─────────────────────────────────────────────────────

@admin_only
async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("فرمت: /block USER_ID")
        return
    uid = int(args[0])
    block_user(uid)
    await update.message.reply_text(f"🚫 کاربر {uid} مسدود شد.")


@admin_only
async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("فرمت: /unblock USER_ID")
        return
    uid = int(args[0])
    unblock_user(uid)
    await update.message.reply_text(f"✅ کاربر {uid} رفع مسدودیت شد.")


# ─── Stats / Info screens ─────────────────────────────────────────────────────

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    text = (
        "📊 *آمار کلی*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 کاربران: {s['total_users']:,}\n\n"
        f"⏳ سفارش در انتظار: {s['pending_orders']}\n"
        f"✅ سفارش تایید‌شده: {s['approved_orders']:,}\n"
        f"❌ سفارش ردشده: {s['rejected_orders']:,}\n\n"
        f"💰 درآمد کل: {fmt_price(s['total_revenue'])}\n"
        f"📦 گیگ فروخته‌شده: {s['total_gb_sold']:,} گیگ\n\n"
        f"💬 تیکت‌های باز: {s['open_tickets']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = get_pending_orders()
    if not orders:
        await update.message.reply_text("✅ هیچ سفارش در انتظاری وجود ندارد.")
        return

    text = f"📋 *سفارشات در انتظار* ({len(orders)} عدد)\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for o in orders:
        uname = f"@{o['username']}" if o.get("username") else "—"
        text += (
            f"🆔 #{o['id']} | {o['full_name']} ({uname})\n"
            f"   📦 {o['gb_amount']} گیگ | 💰 {fmt_price(o['total_price'])}\n"
            f"   ⏰ {o['created_at'][:16]}\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    text = f"👥 *کاربران* ({len(users)} نفر)\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for u in users[:20]:
        uname = f"@{u['username']}" if u.get("username") else "—"
        text += (
            f"• {u['full_name']} — {uname}\n"
            f"  🆔 `{u['user_id']}` | 🛍️ {u['total_orders']} سفارش | 💰 {fmt_price(u['total_spent'])}\n\n"
        )
    if len(users) > 20:
        text += f"... و {len(users)-20} نفر دیگر\n"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_revenue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    avg_order = (
        s["total_revenue"] // s["approved_orders"]
        if s["approved_orders"] else 0
    )
    text = (
        "💰 *گزارش درآمد*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 درآمد کل: {fmt_price(s['total_revenue'])}\n"
        f"📦 گیگ فروش: {s['total_gb_sold']:,} گیگ\n"
        f"🛍️ تعداد سفارش: {s['approved_orders']:,}\n"
        f"📊 میانگین سفارش: {fmt_price(avg_order)}\n"
        f"💡 قیمت هر گیگ: {fmt_price(PRICE_PER_GB)}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_open_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database import _get_conn
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM support_tickets WHERE status='open' ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("✅ هیچ تیکت بازی وجود ندارد.")
        return
    text = f"💬 *تیکت‌های باز* ({len(rows)} عدد)\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    for t in rows:
        uname = f"@{t['username']}" if t["username"] else "—"
        snippet = t["message"][:80].replace("\n", " ")
        text += (
            f"🎫 #{t['id']} — {t['full_name']} ({uname})\n"
            f"   📝 {snippet}...\n"
            f"   /reply_{t['id']} [پاسخ]\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚙️ *راهنمای ادمین*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *مدیریت سفارشات:*\n"
        "  سفارشات جدید با دکمه تایید/رد ارسال می‌شوند.\n"
        "  بعد از تایید، کانفیگ VLESS را ارسال کنید.\n"
        "  سپس لینک Sub را ارسال کنید (یا - برای خالی).\n\n"
        "💬 *پشتیبانی:*\n"
        "  `/reply_ID متن پاسخ`\n\n"
        "🚫 *مسدودسازی:*\n"
        "  `/block USER_ID`\n"
        "  `/unblock USER_ID`\n\n"
        "🎫 *کد تخفیف:*\n"
        "  از منو «ایجاد کد تخفیف» استفاده کنید.\n"
        "  فرمت: `CODE PERCENT MAX_USES`\n\n"
        "📢 *پیام همگانی:*\n"
        "  از منو «پیام همگانی» برای همه کاربران."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=admin_main_kb())


# ─── Deliver config to customer ───────────────────────────────────────────────

async def _deliver_config_to_customer(customer_bot: Bot, order: dict, config: str, sub_link: str):
    uid = order["user_id"]
    gb  = order["gb_amount"]
    msg = (
        f"🎉 *سفارش شما تایید شد!*\n\n"
        f"🆔 شماره سفارش: *#{order['id']}*\n"
        f"📦 حجم: {gb} گیگابایت\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *کانفیگ VLESS شما:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"`{config}`"
    )
    try:
        await customer_bot.send_message(uid, msg, parse_mode="Markdown")
    except Exception as e:
        logger.error("Config delivery failed: %s", e)
        return

    if sub_link:
        try:
            await customer_bot.send_message(
                uid,
                f"🔗 *لینک Subscription:*\n`{sub_link}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error("Sub link delivery failed: %s", e)

    # Send platform guides
    guide_text = (
        "📚 *راهنمای نصب:*\n\n"
        "🍎 *آیفون:*\n"
        "• NPV Tunnel → دریافت از App Store\n"
        "• V2Box → دریافت از App Store\n\n"
        "🤖 *اندروید:*\n"
        "• V2RayNG → دریافت از Google Play\n"
        "• Hiddify → دریافت از Google Play\n\n"
        "🪟 *ویندوز:*\n"
        "• V2RayN → دانلود از GitHub\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "برای راهنمای تصویری کامل، در ربات مشتری\n"
        "روی 📚 *راهنمای نصب* بزنید.\n\n"
        "موفق باشید! 🚀"
    )
    try:
        await customer_bot.send_message(uid, guide_text, parse_mode="Markdown")
    except Exception as e:
        logger.error("Guide delivery failed: %s", e)


# ─── Wire up ──────────────────────────────────────────────────────────────────

def setup_admin_bot(app: Application, customer_bot_instance: Bot = None) -> None:
    if customer_bot_instance:
        app.bot_data["customer_bot_instance"] = customer_bot_instance

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("cancel",  cmd_cancel))
    app.add_handler(CommandHandler("block",   cmd_block))
    app.add_handler(CommandHandler("unblock", cmd_unblock))
    app.add_handler(MessageHandler(
        filters.Regex(r"^/reply_\d+"),
        cmd_reply
    ))
    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(ADMIN_CHAT_ID),
        handle_text
    ))

    logger.info("Admin bot handlers registered.")
